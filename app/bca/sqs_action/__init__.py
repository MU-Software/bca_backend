import boto3
import dataclasses
import enum
import flask
import flask_sqlalchemy as fsql
import json
import sqlalchemy as sql
import typing

import app.common.utils as utils
import app.bca.database.user_db_table as user_db_table
import app.database.profile as profile_module


class UserDBModifyActionCase(enum.Enum):
    add = enum.auto()
    modify = enum.auto()
    delete = enum.auto()


@dataclasses.dataclass
class UserDBModifyData:
    tablename: str
    uuid: int
    action: UserDBModifyActionCase
    column_data_map: dict[str, typing.Any] = dataclasses.field(default_factory=lambda: {})


@dataclasses.dataclass
class UserDBModifyTaskMessage:
    db_owner_id: int
    changes: list[UserDBModifyData]

    def to_dict(self) -> dict:
        if self.db_owner_id < 0:
            raise ValueError('db_owner_id must be bigger than 0')
        if not self.changes:
            raise ValueError('changes must be given')

        changelog = {
            'TB_PROFILE': {},
            'TB_CARD': {},
            'TB_CARD_SUBSCRIPTION': {},
        }

        for change_data in self.changes:
            changelog[change_data.tablename][change_data.uuid] = {
                'action': change_data.action.name,
                'data': change_data.column_data_map
            }

        return {
            'db_owner_id': self.db_owner_id,
            'changelog': changelog
        }

    def add_to_queue(self):
        sqs_client = boto3.client('sqs')
        sqs_client.send_message(
            QueueUrl=flask.current_app.config.get('AWS_TASK_SQS_URL'),
            MessageBody=json.dumps(self.to_dict()),
            MessageGroupId='userdbmod1')


def create_changelog_from_session(db: fsql.SQLAlchemy) -> list[UserDBModifyData]:
    target_tables = {
        'TB_PROFILE': user_db_table.Profile,
        'TB_CARD': user_db_table.Card,
        'TB_CARD_SUBSCRIBED': user_db_table.CardSubscription
    }
    changes: list[UserDBModifyData] = list()

    for row_created in db.session.new:
        if type(row_created).__tablename__ not in target_tables:
            continue

        user_db_target_table = target_tables[type(row_created).__tablename__]

        user_profile_columns = [col_name for col_name, col in user_db_table.Profile.__dict__.items()
                                if isinstance(col, sql.Column)]
        user_card_columns = [col_name for col_name, col in user_db_table.Card.__dict__.items()
                             if isinstance(col, sql.Column)]
        user_cardsubsribe_columns = [col_name for col_name, col in user_db_table.CardSubscription.__dict__.items()
                                     if isinstance(col, sql.Column)]

        if type(row_created).__tablename__ == 'TB_CARD_SUBSCRIBED':
            row_created: profile_module.CardSubscribed = row_created
            # TODO: Add Card and Profile data too
            target_profile: profile_module.Profile = profile_module.Profile.query\
                .filter(profile_module.Profile.uuid == row_created.profile_id)\
                .first()
            target_card: profile_module.Card = profile_module.Card.query\
                .filter(profile_module.Card.uuid == row_created.card_id)\
                .first()
            target_profile_data = {name: getattr(target_profile, name) for name in user_profile_columns}
            target_card_data = {name: getattr(target_card, name) for name in user_card_columns}
            target_cardsubscribe_data = {name: getattr(row_created, name) for name in user_cardsubsribe_columns}
            changes += [
                UserDBModifyData(
                    tablename=user_db_table.Profile.__tablename__,
                    uuid=target_profile.uuid,
                    action=UserDBModifyActionCase.add,
                    column_data_map=target_profile_data),
                UserDBModifyData(
                    tablename=user_db_table.Card.__tablename__,
                    uuid=target_card.uuid,
                    action=UserDBModifyActionCase.add,
                    column_data_map=target_card_data),
                UserDBModifyData(
                    tablename=user_db_table.CardSubscription.__tablename__,
                    uuid=row_created.uuid,
                    action=UserDBModifyActionCase.add,
                    column_data_map=target_cardsubscribe_data)]
        else:
            # Get target user db column lists to restrict columns
            target_columns = [col_name for col_name, col in user_db_target_table.__dict__.items()
                              if isinstance(col, sql.Column)]
            target_data = {name: getattr(row_created, name) for name in target_columns}

            changes.append(
                UserDBModifyData(
                    tablename=user_db_target_table.__tablename__,
                    uuid=row_created.uuid,
                    action=UserDBModifyActionCase.add,
                    column_data_map=target_data))

    for row_modified in db.session.dirty:
        if type(row_modified).__tablename__ not in target_tables:
            continue

        user_db_target_table = target_tables[type(row_modified).__tablename__]
        # Get target user db column lists to restrict columns
        target_columns = [col_name for col_name, col in user_db_target_table.__dict__.items()
                          if isinstance(col, sql.Column)]

        # Instances can be considered dirty although there is no changes,
        # so we need to check it.
        if row_modified.is_modified():
            # Get changes and log it to changelog
            modified_changelog: dict[str, list[typing.Any]] = utils.get_model_changes(row_modified)
            modified_changelog: dict[str, typing.Any] = {k: v[1] for k, v in modified_changelog.items()
                                                         if k in target_columns}

            mod_data = UserDBModifyData(
                tablename=user_db_target_table.__tablename__,
                uuid=row_modified.uuid,
                action=UserDBModifyActionCase.modify,
                column_data_map=modified_changelog)
            changes.append(mod_data)

    for row_deleted in db.session.deleted:
        if type(row_deleted).__tablename__ not in target_tables:
            continue

        user_db_target_table = target_tables[type(row_deleted).__tablename__]

        # TODO: Must delete cards and profiles that are not subscribed to anyone.(NEED_GC)
        changes.append(
            UserDBModifyData(
                tablename=user_db_target_table.__tablename__,
                uuid=row_modified.uuid,
                action=UserDBModifyActionCase.delete))

    return changes
