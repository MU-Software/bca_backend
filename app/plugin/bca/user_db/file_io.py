import base64
import enum
import os
import pathlib as pt
import sqlalchemy as sql
import sqlalchemy.ext.declarative as sqldec
import sqlalchemy.orm as sqlorm
import sqlite3
import tempfile
import typing

import app.common.utils as utils
import app.plugin.bca.user_db.table_def as user_db_table

SYNC_DB_BASE_DIR = pt.Path.cwd() / 'user_content' / 'bca_sync'
SYNC_DB_BASE_KEY = 'user_content/bca_sync/{user_id}/sync_db.sqlite'
SYNC_DB_ID_PATH = lambda user_id: SYNC_DB_BASE_DIR / str(user_id) / 'sync_db.sqlite'  # noqa
SYNC_DB_ID_KEY = lambda user_id: SYNC_DB_BASE_KEY.format(user_id=user_id)  # noqa


class BCaSyncFile:
    user_id: int
    pathobj: pt.Path

    temp_file: tempfile._TemporaryFileWrapper
    s3_bucket_name: str = os.environ.get('AWS_S3_BUCKET_NAME', None)
    s3_region_name: str = os.environ.get('AWS_REGION', None)

    @classmethod
    def create(cls,
               user_id: int,
               insert_all_data_from_global_db: bool = False,
               delete_if_available: bool = False):
        return cls.create_s3(user_id, insert_all_data_from_global_db, delete_if_available)\
            if BCaSyncFile.s3_bucket_name\
            else cls.create_fs(user_id, insert_all_data_from_global_db, delete_if_available)

    @classmethod
    def create_fs(cls,
                  user_id: int,
                  insert_all_data_from_global_db: bool = False,
                  delete_if_available: bool = False):
        self = cls()
        self.user_id = user_id
        self.pathobj = SYNC_DB_ID_PATH(user_id)

        # Check if the file is exist, and if it's exist, then remove it.
        # This won't override `delete_if_available`
        # as local storage can cause exception when there's a file while creating file.
        self.pathobj.parent.mkdir(parents=True, exist_ok=True)
        self.pathobj.unlink(missing_ok=True)
        self.pathobj.open('wb').close()  # Create permanent file

        self.apply_sync_table(insert_all_data_from_global_db)

        return self

    @classmethod
    def create_s3(cls,
                  user_id: int,
                  insert_all_data_from_global_db: bool = False,
                  delete_if_available: bool = False):
        self = cls()
        self.user_id = user_id
        self.temp_file = tempfile.NamedTemporaryFile('w+b', delete=True)
        self.pathobj = pt.Path(self.temp_file.name)

        if delete_if_available:
            BCaSyncFile.delete_s3(user_id)

        self.apply_sync_table(insert_all_data_from_global_db)

        # We need to upload this file object to S3
        # On python, all imports will be cached, so it's OK to import in method.
        import boto3

        with self.pathobj.open('wb') as fp:
            s3 = boto3.client('s3', region_name=BCaSyncFile.s3_region_name)
            bucket = s3.Bucket(BCaSyncFile.s3_bucket_name)
            bucket.upload_fileobj(fp, SYNC_DB_ID_KEY(user_id))

        return self

    @classmethod
    def load(cls, user_id: int):
        return cls.load_s3(user_id) if BCaSyncFile.s3_bucket_name else cls.load_fs(user_id)

    @classmethod
    def load_fs(cls, user_id: int):
        self = cls()
        self.user_id = user_id
        self.pathobj = SYNC_DB_ID_PATH(user_id)

        if not self.pathobj.exists():
            raise FileNotFoundError()

        return self

    @classmethod
    def load_s3(cls, user_id: int):
        self = cls()
        self.user_id = user_id
        self.temp_file = tempfile.NamedTemporaryFile('w+b', delete=True)
        self.pathobj = pt.Path(self.temp_file.name)

        # On python, all imports will be cached, so it's OK to import in method.
        import boto3
        import botocore.client

        try:
            s3 = boto3.client('s3', region_name=BCaSyncFile.s3_region_name)
            bucket = s3.Bucket(BCaSyncFile.s3_bucket_name)

            with self.pathobj.open('wb') as fp:
                bucket.download_fileobj(SYNC_DB_ID_KEY(user_id), fp)
        except botocore.client.ClientError as err:
            if utils.safe_int(err.response['Error']['Code']) == 404:
                raise FileNotFoundError('File or bucket not found on S3')
            raise err
        except Exception as err:
            raise err

        return self

    @utils.class_or_instancemethod
    def check_hash(cls, *, hash_str: str, user_id: typing.Optional[int] = None) -> bool:
        # Notes that hash_str and user_id is keyword-only arguments.
        return cls.get_hash(user_id) == hash_str

    @utils.class_or_instancemethod
    def get_hash(cls, user_id: typing.Optional[int] = None) -> str:
        return cls.get_hash_s3(user_id) if BCaSyncFile.s3_bucket_name else cls.get_hash_fs(user_id)

    @utils.class_or_instancemethod
    def get_hash_fs(self_or_cls, user_id: typing.Optional[int] = None) -> str:
        if isinstance(self_or_cls, type):  # classmethod call
            if user_id is None:
                raise ValueError('user_id must not be None when get_hash_fs method is called as classmethod')
            target_file = SYNC_DB_ID_PATH(user_id)
        else:  # instancemethod call
            if user_id is not None:
                print('user_id will be ignored as BCaSyncFile object has own user_id')
            target_file = SYNC_DB_ID_PATH(self_or_cls.user_id)

        if not target_file.exists():
            BCaSyncFile.create_fs(user_id, True, True)
        return utils.file_md5(target_file)

    @utils.class_or_instancemethod
    def get_hash_s3(self_or_cls, user_id: typing.Optional[int] = None) -> str:
        if isinstance(self_or_cls, type):  # classmethod call
            if user_id is None:
                raise ValueError('user_id must not be None when get_hash_s3 method is called as classmethod')

            # When we call this method as classmethod, then we need to pull hash from AWS S3.
            # On python, all imports will be cached, so it's OK to import in method.
            import boto3
            import botocore.client

            try:
                s3_client = boto3.client('s3', region_name=BCaSyncFile.s3_region_name)
                return s3_client.head_object(
                    Bucket=BCaSyncFile.s3_bucket_name,
                    Key=SYNC_DB_ID_KEY(user_id))['ETag'][1:-1]
            except botocore.client.ClientError as err:
                if utils.safe_int(err.response['Error']['Code']) == 404:
                    raise FileNotFoundError()
                raise err
            except Exception as err:
                raise err
        else:  # instancemethod call
            if user_id is not None:
                print('user_id will be ignored as BCaSyncFile object has own user_id')

            # When we call this method as instancemethod,
            # then we need to calculate hash from temp file as we have a copy of the file on temp file.
            if not self_or_cls.pathobj.exists():
                raise FileNotFoundError()
            return utils.file_md5(self_or_cls.pathobj)

    @utils.class_or_instancemethod
    def delete(cls, user_id: typing.Optional[int] = None):
        cls.delete_s3(user_id) if BCaSyncFile.s3_bucket_name else cls.delete_fs(user_id)

    @utils.class_or_instancemethod
    def delete_fs(self_or_cls, user_id: typing.Optional[int] = None):
        if isinstance(self_or_cls, type):  # classmethod call
            if user_id is None:
                raise ValueError('user_id must not be None when delete_fs method is called as classmethod')
            SYNC_DB_ID_PATH(user_id).unlink(missing_ok=True)
        else:  # instancemethod call
            if user_id is not None:
                print('user_id will be ignored as BCaSyncFile object has own user_id')
            self_or_cls.pathobj.unlink(missing_ok=True)

    @utils.class_or_instancemethod
    def delete_s3(self_or_cls, user_id: typing.Optional[int] = None):
        if isinstance(self_or_cls, type):  # classmethod call
            if user_id is None:
                raise ValueError('user_id must not be None when delete_s3 method is called as classmethod')
        else:  # instancemethod call
            if user_id is not None:
                print('user_id will be ignored as BCaSyncFile object has own user_id')
            user_id = self_or_cls.user_id

        # On python, all imports will be cached, so it's OK to import in method.
        import boto3
        import botocore.client

        try:
            s3_client = boto3.client('s3', region_name=BCaSyncFile.s3_region_name)
            s3_client.delete_object(Bucket=BCaSyncFile.s3_bucket_name, Key=SYNC_DB_ID_KEY(user_id))
        except botocore.client.ClientError as err:
            if utils.safe_int(err.response['Error']['Code']) == 404:
                return
            raise err
        except Exception as err:
            raise err

    def upload_to_s3(self):
        import boto3
        s3 = boto3.client('s3', region_name=self.s3_region_name)
        bucket = s3.Bucket(self.s3_bucket_name)

        with self.pathobj.open('rb') as fp:
            bucket.upload_fileobj(fp, SYNC_DB_ID_KEY(self.user_id))

    def as_b64urlsafe(self) -> str:
        if not self.pathobj.exists():
            raise FileNotFoundError()

        return base64.b64encode(self.pathobj.read_bytes()).decode()

    def apply_sync_table(self, insert_all_data_from_global_db: bool = False):
        '''
        This opens file and creates B.Ca sync tables,
        and insert sync data from global db if `insert_all_data_from_global_db` is true.
        '''
        temp_user_db_sqlite_conn = sqlite3.connect(self.pathobj)
        temp_user_db_engine = sql.create_engine('sqlite://', creator=lambda: temp_user_db_sqlite_conn)
        temp_user_db_session = sqlorm.scoped_session(
                                    sqlorm.sessionmaker(
                                        autocommit=False,
                                        autoflush=False,
                                        bind=temp_user_db_engine))
        temp_user_db_base = sqldec.declarative_base()

        # Create tables
        ProfileTable = type(
            'ProfileTable',
            (temp_user_db_base, user_db_table.Profile),
            {})
        ProfileRelationTable = type(
            'ProfileRelationTable',
            (temp_user_db_base, user_db_table.ProfileRelation),
            {})
        CardTable = type(
            'CardTable',
            (temp_user_db_base, user_db_table.Card),
            {})
        CardSubscriptionTable = type(
            'CardSubscriptionTable',
            (temp_user_db_base, user_db_table.CardSubscription),
            {})

        ProfileTable.__table__.create(temp_user_db_engine)
        ProfileRelationTable.__table__.create(temp_user_db_engine)
        CardTable.__table__.create(temp_user_db_engine)
        CardSubscriptionTable.__table__.create(temp_user_db_engine)

        if insert_all_data_from_global_db:
            # Insert data to user db from global db
            # Find user's profiles, and find all card subscriptions using user's profiles.
            # Hopefully, we unnormalized columns, so we can query this easily... rignt?

            # Import db_module and profile_module in this method to make this module file as portable as possible.
            import app.database as db_module
            import app.database.bca.profile as profile_module
            db = db_module.db

            # All profile's ID that created by user, following profiles, and subscribed cards' profiles
            user_profiles_query = db.session.query(profile_module.Profile.uuid)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .filter(profile_module.Profile.user_id == self.user_id)\
                .subquery()

            following_profiles_query = db.session.query(profile_module.ProfileRelation.to_profile_id)\
                .filter(profile_module.ProfileRelation.from_user_id == self.user_id)\
                .join(profile_module.ProfileRelation.to_profile, aliased=True)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .distinct().subquery()

            subscribed_cards_profiles_query = db.session.query(profile_module.CardSubscription.card_profile_id)\
                .filter(profile_module.CardSubscription.subscribed_user_id == self.user_id)\
                .join(profile_module.CardSubscription.card, aliased=True)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .distinct().subquery()

            # All profiles to be loaded
            load_target_profiles: list[profile_module.Profile] = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(sql.or_(
                    profile_module.Profile.uuid.in_(user_profiles_query),
                    profile_module.Profile.uuid.in_(following_profiles_query),
                    profile_module.Profile.uuid.in_(subscribed_cards_profiles_query),
                )).distinct(profile_module.Profile.uuid).all()

            # All profile relations to be loaded
            load_target_profile_relations: list[profile_module.ProfileRelation] = db.session.query(
                profile_module.ProfileRelation)\
                .filter(profile_module.ProfileRelation.from_user_id == self.user_id)\
                .join(profile_module.ProfileRelation.to_profile, aliased=True)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .distinct(profile_module.ProfileRelation.uuid).all()

            # All card subscriptions to be loaded
            card_subscriptions_query = db.session.query(profile_module.CardSubscription)\
                .filter(profile_module.CardSubscription.subscribed_user_id == self.user_id)\
                .join(profile_module.CardSubscription.card, aliased=True)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .distinct(profile_module.CardSubscription.uuid)

            load_target_card_subscriptions: list[profile_module.CardSubscription] = card_subscriptions_query.all()

            # All cards to be loaded
            load_target_cards: list[profile_module.Card] = db.session.query(profile_module.Card)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .filter(sql.or_(
                    profile_module.Card.user_id == self.user_id,  # User's cards
                    profile_module.Card.uuid.in_(  # Subscribed cards
                        card_subscriptions_query.with_entities(profile_module.CardSubscription.uuid)),
                ))\
                .distinct(profile_module.Card.uuid).all()

            load_target_table_map: list[tuple[list, typing.Type]] = [
                (load_target_profiles, ProfileTable),
                (load_target_profile_relations, ProfileRelationTable),
                (load_target_cards, CardTable),
                (load_target_card_subscriptions, CardSubscriptionTable),
            ]
            for load_target_data_list, TableClass in load_target_table_map:
                for load_target_data in load_target_data_list:
                    new_row = TableClass()

                    for column in TableClass.column_names:
                        result_val = getattr(load_target_data, column)
                        if isinstance(result_val, enum.Enum):
                            result_val = result_val.value
                        setattr(new_row, column, result_val)

                    temp_user_db_session.add(new_row)

            temp_user_db_session.commit()
            temp_user_db_engine.dispose()  # Disconnect all connections (for safety)
