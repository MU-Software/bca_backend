import datetime
import enum
import flask
import flask_sqlalchemy as fsql
import json
import sqlite3
import typing

import celery
import redis
import redis_lock
import sqlalchemy as sql
import sqlalchemy.ext.declarative as sqldec
import sqlalchemy.orm as sqlorm

import app.common.utils as utils
import app.plugin.bca.user_db.celery_init as celery_init
import app.database as db_module
import app.database.bca.profile as profile_module
import app.plugin.bca.user_db.table_def as user_db_table
import app.plugin.bca.user_db.file_io as user_db_file_io
import app.plugin.bca.user_db.table_def as user_db_table_def

db = db_module.db
celery_app: celery.Celery = celery_init.init_celery_app()
CeleryTask = celery_init.CeleryTask

USER_DB_JOURNAL_DATA_DICT_TYPE = typing.TypedDict('USER_DB_MODIFY_DATA_DICT_TYPE', {
    'tablename': str,
    'uuid': int,
    'action': typing.Literal['add', 'modify', 'delete'],
    'column_map_data': dict[str, typing.Any]
})

# Python doesn't support Type-hinting of nested TypedDict now.(CPython 3.10)
USER_DB_JOURNAL_CHANGEDATA_DICT_TYPE = typing.TypedDict('USER_DB_JOURNAL_CHANGEDATA_DICT_TYPE', {
    'action': typing.Literal['add', 'modify', 'delete'],
    'data': typing.Any
})
USER_DB_JOURNAL_CHANGEDATA_COLLECTION_DICT_TYPE = dict[int, USER_DB_JOURNAL_CHANGEDATA_DICT_TYPE]
USER_DB_JOURNAL_CHANGELOG_DICT_TYPE = typing.TypedDict('USER_DB_JOURNAL_CHANGELOG_DICT_TYPE', {
    'TB_PROFILE': USER_DB_JOURNAL_CHANGEDATA_COLLECTION_DICT_TYPE,
    'TB_PROFILE_RELATION': USER_DB_JOURNAL_CHANGEDATA_COLLECTION_DICT_TYPE,
    'TB_CARD': USER_DB_JOURNAL_CHANGEDATA_COLLECTION_DICT_TYPE,
    'TB_CARD_SUBSCRIPTION': USER_DB_JOURNAL_CHANGEDATA_COLLECTION_DICT_TYPE,
})
USER_DB_JOURNAL_DICT_TYPE = typing.TypedDict('USER_DB_JOURNAL_DICT_TYPE', {
    'db_owner_id': int,
    'changelog': USER_DB_JOURNAL_CHANGELOG_DICT_TYPE
})

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
USER_DB_TASK_SET_EXPIRE_TIMEDELTA = datetime.timedelta(minutes=10)


class UserDBJournalActionCase(utils.EnumAutoName):
    add = enum.auto()
    modify = enum.auto()
    delete = enum.auto()


class UserDBJournalChangelogData:
    tablename: str
    uuid: int
    action: UserDBJournalActionCase
    column_data_map: dict[str, typing.Any]

    @classmethod
    def from_dict(cls, dict_in: USER_DB_JOURNAL_DATA_DICT_TYPE):
        self = cls()

        self.tablename = dict_in['tablename']
        self.uuid = dict_in['uuid']
        self.action = UserDBJournalActionCase(dict_in['action'])
        self.column_data_map = dict_in['column_data_map']

        return self

    def apply(self, session: sqlorm.scoped_session, tables: dict[str, sqldec.DeclarativeMeta]):
        table_cls = tables[self.tablename]
        target_table_row: table_cls = None

        if self.action == UserDBJournalActionCase.add:
            target_table_row = table_cls()
            session.add(target_table_row)
        elif self.action == UserDBJournalActionCase.modify:
            target_table_row = session.query(table_cls).filter(table_cls.uuid == self.uuid).first()
        elif self.action == UserDBJournalActionCase.delete:
            session.query(table_cls).filter(table_cls.uuid == self.uuid).delete(synchronize_session='fetch')
            session.commit()
            return
        else:
            return

        for k, v in self.column_data_map.items():
            setattr(target_table_row, k, v)

        session.commit()


class UserDBJournal:
    task_id: str
    db_owner_id: int
    changes: list[UserDBJournalChangelogData]

    @classmethod
    def from_dict(cls, dict_in: USER_DB_JOURNAL_DICT_TYPE):
        self = cls()
        self.db_owner_id = dict_in['db_owner_id']
        self.changes = list()

        for mod_data_tb_name, mod_data_tb_data in dict_in['changelog'].items():
            mod_data_tb_data: USER_DB_JOURNAL_CHANGELOG_DICT_TYPE = mod_data_tb_data  # Force type-hint

            for row_uuid, changelog in mod_data_tb_data.items():
                changelog: USER_DB_JOURNAL_CHANGEDATA_DICT_TYPE = changelog  # Force type-hint
                self.changes.append(UserDBJournalChangelogData.from_dict({
                    'tablename': mod_data_tb_name,
                    'uuid': row_uuid,
                    'action': UserDBJournalActionCase(changelog['action']),
                    'data': changelog['data']
                }))

        return self

    @classmethod
    def from_json(cls, json_str: str) -> list['UserDBJournal']:
        json_data: typing.Union[list[dict], dict] = json.loads(json_str)
        result: list[cls] = list()

        if isinstance(json_data, list):
            result = [cls.from_dict(msg) for msg in json_data]
        elif isinstance(json_data, dict):
            result = [cls.from_dict(json_data), ]
        else:
            raise TypeError(f'{cls.__name__}.from_json only accepts array/object json string')

        return result

    def to_dict(self) -> USER_DB_JOURNAL_DICT_TYPE:
        if self.db_owner_id < 0:
            raise ValueError('db_owner_id must be bigger than 0')
        if not self.changes:
            raise ValueError('changes must be given')

        changelog = {
            'TB_PROFILE': {},
            'TB_PROFILE_RELATION': {},
            'TB_CARD': {},
            'TB_CARD_SUBSCRIPTION': {},
        }

        for change_data in self.changes:
            changelog[change_data.tablename][change_data.uuid] = {
                'action': change_data.action,
                'data': change_data.column_data_map
            }

        return {
            'db_owner_id': self.db_owner_id,
            'changelog': changelog
        }

    def add_to_queue(self):
        task_job_data = json.dumps(self.to_dict(), default=utils.json_default, ensure_ascii=False)

        AWS_TASK_SQS_URL = flask.current_app.config.get('AWS_TASK_SQS_URL', None)
        if AWS_TASK_SQS_URL:
            import boto3
            sqs_client = boto3.client('sqs')
            sqs_client.send_message(
                QueueUrl=AWS_TASK_SQS_URL,
                MessageBody=task_job_data,
                MessageGroupId='userdbmod1')
        else:
            UserDBJournal.run.delay(task_job_data)

    @staticmethod
    @celery_app.task()
    def run(dict_in: USER_DB_JOURNAL_DICT_TYPE):
        self = UserDBJournal.from_dict(dict_in)

        # What we should do here is...
        # 1. Wait redis lock and acquire
        # 2. Get target DB file from File System or S3
        # 3. Create SQLAlchemy ORM object
        # 4. Re-Order tasks
        # 5. Apply those tasks
        # 6. Save or Upload it
        # 7. Check if there's another pending tasks,
        #    and if there's no pending tasks to this user, then send push to target user.
        # Now, Let's do this

        # Wait redis lock and acquire
        redis_conn = redis.StrictRedis(
            host=flask.current_app.config.get('REDIS_HOST'),
            port=flask.current_app.config.get('REDIS_PORT'),
            password=flask.current_app.config.get('REDIS_PASSWORD'),
            db=flask.current_app.config.get('REDIS_DB'))
        user_db_key = user_db_file_io.SYNC_DB_ID_KEY(self.db_owner_id)
        user_db_task_set_key = user_db_key + ':TASK_SETS'
        # It's OK to append task id on the redis set without lock.
        # But, don't forget to update expire time!
        # We need to set expire time to prevent this set left forever,
        # so we need to set newly created sets, and update exp time everytime when we add a new task id.
        redis_conn.sadd(user_db_task_set_key, self.task_id)
        redis_conn.expire(user_db_task_set_key, USER_DB_TASK_SET_EXPIRE_TIMEDELTA)

        with redis_lock.Lock(redis_conn, user_db_key):
            try:
                # Get target DB file from File System or S3
                target_file = user_db_file_io.BCaSyncFile.load(self.db_owner_id)

                # Create SQLAlchemy ORM object
                user_db_orm_sqlite_conn = sqlite3.connect(target_file)
                user_db_orm_engine = sql.create_engine('sqlite://', creator=lambda: user_db_orm_sqlite_conn)
                user_db_orm_session = sqlorm.scoped_session(
                                            sqlorm.sessionmaker(
                                                autocommit=False,
                                                autoflush=False,
                                                bind=user_db_orm_engine))
                user_db_orm_base = sqldec.declarative_base(bind=user_db_orm_engine)
                user_db_orm_tables = {
                    'TB_PROFILE': type(
                        'ProfileTable', (user_db_orm_base, user_db_table_def.Profile), {}),
                    'TB_PROFILE_RELATION': type(
                        'ProfileRelationTable', (user_db_orm_base, user_db_table_def.ProfileRelation), {}),
                    'TB_CARD': type(
                        'CardTable', (user_db_orm_base, user_db_table_def.Card), {}),
                    'TB_CARD_SUBSCRIPTION': type(
                        'CardSubscriptionTable', (user_db_orm_base, user_db_table_def.CardSubscription), {})
                }

                # Re-Order tasks
                # We need to handle changelog this order to avoid FK error
                # 1. profile insertion/modification
                #    - TB_PROFILE, UserDBJournalActionCase.(add | modify)
                # 2. card insertion
                #    - TB_CARD, UserDBJournalActionCase.(add | modify)
                # 3. profile relation insertion/deletion/modification
                #    - TB_PROFILE_RELATION, UserDBJournalActionCase.(add | modify | delete)
                # 4. card subscription insertion/deletion/modification
                #    - TB_CARD_SUBSCRIPTION, UserDBJournalActionCase.(add | modify | delete)
                # 5. profile deletion
                #    - TB_PROFILE, UserDBJournalActionCase.(delete)
                # 6. card deletion
                #    - TB_CARD, UserDBJournalActionCase.(delete)
                # Let's order it.
                TASK_ORDER: list[tuple[str, tuple[UserDBJournalActionCase]]] = [
                    ('TB_PROFILE', (
                        UserDBJournalActionCase.add,
                        UserDBJournalActionCase.modify))
                    ('TB_CARD', (
                        UserDBJournalActionCase.add,
                        UserDBJournalActionCase.modify)),
                    ('TB_PROFILE_RELATION', (
                        UserDBJournalActionCase.add,
                        UserDBJournalActionCase.modify,
                        UserDBJournalActionCase.delete)),
                    ('TB_CARD_SUBSCRIPTION', (
                        UserDBJournalActionCase.add,
                        UserDBJournalActionCase.modify,
                        UserDBJournalActionCase.delete)),
                    ('TB_PROFILE', (
                        UserDBJournalActionCase.delete)),
                    ('TB_CARD', (
                        UserDBJournalActionCase.delete)),
                ]

                ordered_tasks: list[UserDBJournalChangelogData] = list()
                for task_order_type in TASK_ORDER:
                    target_tb_changelog = [
                        mtm for mtm in self.changes
                        if mtm.tablename in task_order_type[0]
                        and mtm.action in task_order_type[1]]
                    ordered_tasks += target_tb_changelog

                # OK, now task is ordered, let's apply it.
                for ordered_task in ordered_tasks:
                    ordered_task.apply(user_db_orm_session, user_db_orm_tables)

                # Clean up the changes on DB and disconnect it.
                user_db_orm_session.commit()
                user_db_orm_engine.dispose()

                # Save or upload it.
                # If the file is on a local storage, then changes will be applied automatically,
                # but we should upload if the file came from S3
                if target_file.s3_bucket_name:
                    target_file.upload_to_s3()

                # Task complete, check if there's another pending tasks,
                # and if there's no pending tasks to this user, then send push to target user.
                # Notes: If the set is empty on redis, then redis will remove that set entity,
                #        so if we delete the last item on set, then redis will remove that set entity.
                redis_conn.srem(user_db_task_set_key, self.task_id)
                if not redis_conn.exists(user_db_task_set_key):
                    # There's no pending tasks! Send push to user!
                    try:
                        pass
                    except Exception as push_err:
                        # Just log this as warning and ignore this error, as it's not a important part.
                        print(utils.get_traceback_msg(push_err))
            except Exception as err:
                print(utils.get_traceback_msg(err))
                # TODO: We need to retry this task
                raise err


class UserDBJournalCreator:
    db: fsql.SQLAlchemy = None
    session_added: list[db.Model] = None
    session_modified: list[db.Model] = None
    session_deleted: list[db.Model] = None

    def __init__(self, db: fsql.SQLAlchemy):
        self.db = db

    def __enter__(self):
        # Dirty way to copy list of added/modified/deleted rows on session
        self.session_added = [r for r in db.session.new]
        self.session_modified = [r for r in db.session.dirty]
        self.session_deleted = [r for r in db.session.deleted]

    def __exit__(self, ex_type, ex_value, ex_traceback):
        taskmsg = self.get_journal_from_rowlist()
        for k, v in taskmsg.items():
            v.add_to_queue()

    def get_journal_from_rowlist(self) -> dict[int, UserDBJournal]:
        modify_journal: dict[int, UserDBJournal] = dict()

        for row in self.session_added:
            if not isinstance(row, (*TARGET_TABLE_MAP.keys(), )):
                continue

            UserDBTableClass = TARGET_TABLE_MAP[row.__class__]['user_db_table_class']
            db_owner_id_target_list = TARGET_TABLE_MAP[row.__class__]['db_owner_id_calc']['c'](row)

            db_mod_data = UserDBJournalChangelogData()
            db_mod_data.tablename = TARGET_TABLE_MAP[row.__class__]['user_db_table_class'].__tablename__
            db_mod_data.uuid = getattr(row, 'uuid')
            db_mod_data.action = UserDBJournalActionCase.add.value
            db_mod_data.column_data_map = dict()

            for column in UserDBTableClass.column_names:
                db_mod_data.column_data_map[column] = getattr(row, column)

            for user_id in db_owner_id_target_list:
                if user_id not in modify_journal:
                    modify_journal[user_id] = UserDBJournal()
                    modify_journal[user_id].db_owner_id = user_id
                    modify_journal[user_id].changes = list()

                modify_journal[user_id].changes.append(db_mod_data)

            # If the table is ProfileRelation or CardSubscription,
            # then we need to add Profile and Card row on user db too.
            if isinstance(row, (profile_module.ProfileRelation, profile_module.CardSubscription)):
                target_rows = list()
                db_owner_id_target = list()
                if isinstance(row, profile_module.ProfileRelation):
                    target_rows.append(row.to_profile)
                    db_owner_id_target.append(row.from_user_id)
                else:
                    target_rows.append(row.card)
                    target_rows.append(row.card_profile)
                    db_owner_id_target.append(row.subscribed_user_id)

                for target_row in target_rows:
                    UserDBTableClass = TARGET_TABLE_MAP[row.__class__]['user_db_table_class']

                    db_mod_data = UserDBJournalChangelogData()
                    db_mod_data.tablename = TARGET_TABLE_MAP[row.__class__]['user_db_table_class'].__tablename__
                    db_mod_data.uuid = getattr(row, 'uuid')
                    db_mod_data.action = UserDBJournalActionCase.add.value
                    db_mod_data.column_data_map = dict()

                    for column in UserDBTableClass.column_names:
                        db_mod_data.column_data_map[column] = getattr(row, column)

                    for user_id in db_owner_id_target:
                        if user_id not in modify_journal:
                            modify_journal[user_id] = UserDBJournal()
                            modify_journal[user_id].db_owner_id = user_id
                            modify_journal[user_id].changes = list()

                        modify_journal[user_id].changes.append(db_mod_data)

        for row in self.session_modified:
            if not isinstance(row, tuple(TARGET_TABLE_MAP)):
                continue

            UserDBTableClass = TARGET_TABLE_MAP[row.__class__]['user_db_table_class']
            db_owner_id_target_list = TARGET_TABLE_MAP[row.__class__]['db_owner_id_calc']['u'](row)

            db_mod_data = UserDBJournalChangelogData()
            db_mod_data.tablename = TARGET_TABLE_MAP[row.__class__]['user_db_table_class'].__tablename__
            db_mod_data.uuid = getattr(row, 'uuid')
            db_mod_data.action = UserDBJournalActionCase.modify.value
            db_mod_data.column_data_map = dict()

            for column in UserDBTableClass.column_names:
                db_mod_data.column_data_map[column] = getattr(row, column)

            for user_id in db_owner_id_target_list:
                if user_id not in modify_journal:
                    modify_journal[user_id] = UserDBJournal()
                    modify_journal[user_id].db_owner_id = user_id
                    modify_journal[user_id].changes = list()

                modify_journal[user_id].changes.append(db_mod_data)

        for row in self.session_deleted:
            if not isinstance(row, tuple(TARGET_TABLE_MAP)):
                continue

            UserDBTableClass = TARGET_TABLE_MAP[row.__class__]['user_db_table_class']
            db_owner_id_target_list = TARGET_TABLE_MAP[row.__class__]['db_owner_id_calc']['d'](row)

            db_mod_data = UserDBJournalChangelogData()
            db_mod_data.tablename = TARGET_TABLE_MAP[row.__class__]['user_db_table_class'].__tablename__
            db_mod_data.uuid = getattr(row, 'uuid')
            db_mod_data.action = UserDBJournalActionCase.delete.value
            db_mod_data.column_data_map = dict()

            for column in UserDBTableClass.column_names:
                db_mod_data.column_data_map[column] = getattr(row, column)

            for user_id in db_owner_id_target_list:
                if user_id not in modify_journal:
                    modify_journal[user_id] = UserDBJournal()
                    modify_journal[user_id].db_owner_id = user_id
                    modify_journal[user_id].changes = list()

                modify_journal[user_id].changes.append(db_mod_data)

        return modify_journal
