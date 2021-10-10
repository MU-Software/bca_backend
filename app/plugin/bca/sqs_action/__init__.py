import boto3
import dataclasses
import enum
import flask
import flask_sqlalchemy as fsql
import json
import typing

import app.common.utils as utils
import app.plugin.bca.database.user_db_table as user_db_table
import app.database as db_module
import app.database.bca.profile as profile_module

db = db_module.db

# Target tables list
TARGET_TABLE_MAP = {
    profile_module.Profile: {
        'user_db_table_class': user_db_table.Profile,
        'db_owner_id_calc': {
            'c': lambda row: [row.user_id, ],
            'u': lambda row: [*db.session.query(profile_module.ProfileRelation.from_user_id).distinct()
                              .filter(profile_module.ProfileRelation.to_user_id == row.user_id).all(), row.user_id],
            'd': lambda row: [*db.session.query(profile_module.ProfileRelation.from_user_id).distinct()
                              .filter(profile_module.ProfileRelation.to_user_id == row.user_id).all(), row.user_id],
        }
    },
    profile_module.ProfileRelation: {
        'user_db_table_class': user_db_table.ProfileRelation,
        'db_owner_id_calc': {
            'c': lambda row: [row.user_id, ],
            'u': lambda row: [row.user_id, ],
            'd': lambda row: [row.user_id, ],
        }
    },
    profile_module.Card: {
        'user_db_table_class': user_db_table.Card,
        'db_owner_id_calc': {
            'c': lambda row: [row.user_id, ],
            'u': lambda row: [db.session.query(profile_module.CardSubscription.subscribed_user_id).distinct()
                              .filter(profile_module.CardSubscription.card_user_id == row.user_id).all(), row.user_id],
            'd': lambda row: [db.session.query(profile_module.CardSubscription.subscribed_user_id).distinct()
                              .filter(profile_module.CardSubscription.card_user_id == row.user_id).all(), row.user_id],
        }
    },
    profile_module.CardSubscription: {
        'user_db_table_class': user_db_table.CardSubscription,
        'db_owner_id_calc': {
            'c': lambda row: [row.user_id, ],
            'u': lambda row: [row.user_id, ],
            'd': lambda row: [row.user_id, ],
        }
    }
}


class UserDBModifyActionCase(utils.EnumAutoName):
    add = enum.auto()
    modify = enum.auto()
    delete = enum.auto()


class UserDBModifyData:
    tablename: str
    uuid: int
    action: str
    column_data_map: dict[str, typing.Any] = dataclasses.field(default_factory=lambda: {})


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
            'TB_PROFILE_SUBSCRIPTION': {},
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
            MessageBody=json.dumps(self.to_dict(), default=utils.json_default),
            MessageGroupId='userdbmod1')


def get_journal_from_rowlist(
        session_added: list[typing.Type[db.Model]] = None,
        session_modified: list[typing.Type[db.Model]] = None,
        session_deleted: list[typing.Type[db.Model]] = None) -> dict[int, UserDBModifyTaskMessage]:
    modify_journal: dict[int, UserDBModifyTaskMessage] = dict()

    for row in session_added:
        if not isinstance(row, tuple(TARGET_TABLE_MAP)):
            continue

        UserDBTableClass = TARGET_TABLE_MAP[row.__class__]['user_db_table_class']
        db_owner_id_target_list = TARGET_TABLE_MAP[row.__class__]['db_owner_id_calc']['c']()

        db_mod_data = UserDBModifyData()
        db_mod_data.tablename = TARGET_TABLE_MAP[row.__class__].__tablename__
        db_mod_data.uuid = getattr(row, 'uuid')
        db_mod_data.action = UserDBModifyActionCase.add.value()
        db_mod_data.column_data_map = dict()

        for column in UserDBTableClass.column_names:
            db_mod_data.column_data_map[column] = getattr(row, column)

        for user_id in db_owner_id_target_list:
            if user_id not in modify_journal:
                modify_journal[user_id] = UserDBModifyTaskMessage()
                modify_journal[user_id].db_owner_id = user_id
                modify_journal[user_id].changes = list()

            modify_journal[user_id].changes.append(db_mod_data)

    for row in session_modified:
        if not isinstance(row, tuple(TARGET_TABLE_MAP)):
            continue

        UserDBTableClass = TARGET_TABLE_MAP[row.__class__]['user_db_table_class']
        db_owner_id_target_list = TARGET_TABLE_MAP[row.__class__]['db_owner_id_calc']['u']()

        db_mod_data = UserDBModifyData()
        db_mod_data.tablename = TARGET_TABLE_MAP[row.__class__].__tablename__
        db_mod_data.uuid = getattr(row, 'uuid')
        db_mod_data.action = UserDBModifyActionCase.modify.value()
        db_mod_data.column_data_map = dict()

        for column in UserDBTableClass.column_names:
            db_mod_data.column_data_map[column] = getattr(row, column)

        for user_id in db_owner_id_target_list:
            if user_id not in modify_journal:
                modify_journal[user_id] = UserDBModifyTaskMessage()
                modify_journal[user_id].db_owner_id = user_id
                modify_journal[user_id].changes = list()

            modify_journal[user_id].changes.append(db_mod_data)

    for row in session_deleted:
        if not isinstance(row, tuple(TARGET_TABLE_MAP)):
            continue

        UserDBTableClass = TARGET_TABLE_MAP[row.__class__]['user_db_table_class']
        db_owner_id_target_list = TARGET_TABLE_MAP[row.__class__]['db_owner_id_calc']['d']()

        db_mod_data = UserDBModifyData()
        db_mod_data.tablename = TARGET_TABLE_MAP[row.__class__].__tablename__
        db_mod_data.uuid = getattr(row, 'uuid')
        db_mod_data.action = UserDBModifyActionCase.delete.value()
        db_mod_data.column_data_map = dict()

        for column in UserDBTableClass.column_names:
            db_mod_data.column_data_map[column] = getattr(row, column)

        for user_id in db_owner_id_target_list:
            if user_id not in modify_journal:
                modify_journal[user_id] = UserDBModifyTaskMessage()
                modify_journal[user_id].db_owner_id = user_id
                modify_journal[user_id].changes = list()

            modify_journal[user_id].changes.append(db_mod_data)


class UserDBJournalCreator:
    db: fsql.SQLAlchemy = None
    session_added: list[typing.Type[db.Model]] = None
    session_modified: list[typing.Type[db.Model]] = None
    session_deleted: list[typing.Type[db.Model]] = None

    def __init__(self, db: fsql.SQLAlchemy):
        self.db = db

    def __enter__(self):
        # Dirty way to copy list of added/modified/deleted rows on session
        self.session_added = [r for r in db.session.new]
        self.session_modified = [r for r in db.session.dirty]
        self.session_deleted = [r for r in db.session.deleted]

    def __exit__(self, ex_type, ex_value, ex_traceback):
        taskmsg = get_journal_from_rowlist(self.session_added, self.session_modified, self.session_deleted)
        for k, v in taskmsg.items():
            v.add_to_queue()
