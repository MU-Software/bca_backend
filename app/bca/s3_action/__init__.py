import boto3
import botocore.client
import flask
import io
import pathlib as pt
import sqlalchemy as sql
import sqlalchemy.ext.declarative as sqldec
import sqlalchemy.orm as sqlorm
import sqlite3
import tempfile
import typing

import app.common.utils as utils
import app.database as db_module
import app.database.profile as profile_module
import app.bca.database.user_db_table as bca_user_db_table


def create_user_db(user_id: int,
                   insert_all_data_from_global_db: bool = False,
                   delete_if_available: bool = False) -> typing.Optional[typing.IO[bytes]]:
    # bca: create user's db file and upload to s3
    try:
        if delete_if_available:
            delete_user_db(user_id)

        # Create temporary file and connection
        temp_user_db_file = tempfile.NamedTemporaryFile('w+b', delete=True)
        temp_user_db_sqlite_conn = sqlite3.connect(temp_user_db_file.name)
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
            (temp_user_db_base, bca_user_db_table.Profile),
            {})
        CardTable = type(
            'CardTable',
            (temp_user_db_base, bca_user_db_table.Card),
            {})
        CardSubscriptionTable = type(
            'CardSubscriptionTable',
            (temp_user_db_base, bca_user_db_table.CardSubscription),
            {})

        ProfileTable.__table__.create(temp_user_db_engine)
        CardTable.__table__.create(temp_user_db_engine)
        CardSubscriptionTable.__table__.create(temp_user_db_engine)

        if insert_all_data_from_global_db:
            # Insert data to user db from global db
            # Find user's profiles, and find all card subscriptions using user's profiles.

            # List of profile's ID that owned by user
            user_profiles_query = db_module.db.session.query(profile_module.Profile.uuid)\
                .filter(profile_module.Profile.locked_at == None)\
                .filter(profile_module.Profile.deleted_at == None)\
                .filter(profile_module.Profile.user_id == user_id)\
                .subquery()  # noqa

            # All relations between profiles (owned by user) and cards
            user_card_relations_query = profile_module.CardSubscription.query\
                .filter(profile_module.CardSubscription.profile_id.in_(user_profiles_query))

            # All card id that needs to be added to user DB
            card_ids_that_needs_to_be_added_query = user_card_relations_query\
                .with_entities(profile_module.CardSubscription.card_id)

            user_subscripting_cards_query = profile_module.Card.query\
                .filter(
                    (profile_module.Card.uuid.in_(card_ids_that_needs_to_be_added_query))
                    | (profile_module.Card.profile_id.in_(user_profiles_query)))\
                .filter(profile_module.Card.locked_at == None)  # noqa

            # All profile id that needs to be added to user DB
            profile_ids_that_needs_to_be_added_query = user_card_relations_query\
                .with_entities(profile_module.CardSubscription.profile_id)

            user_following_profiles_query = profile_module.Profile.query\
                .filter(
                    (profile_module.Profile.uuid.in_(profile_ids_that_needs_to_be_added_query))
                    | (profile_module.Profile.user_id == user_id))\
                .filter(profile_module.Profile.locked_at == None)  # noqa

            user_card_relations: list[profile_module.CardSubscription] = user_card_relations_query.all()
            user_subscripting_cards: list[profile_module.Card] = user_subscripting_cards_query\
                .distinct(profile_module.Card.uuid).all()
            user_following_profiles: list[profile_module.Profile] = user_following_profiles_query\
                .distinct(profile_module.Profile.uuid).all()

            for profile in user_following_profiles:
                new_profile = ProfileTable()

                target_columns = (
                    'uuid', 'description', 'data',
                    'name', 'email', 'phone', 'sns',
                    'commit_id', 'created_at', 'modified_at',
                    'deleted_at', 'why_deleted',
                    'guestbook', 'announcement', 'private')

                for column in target_columns:
                    setattr(new_profile, column, getattr(profile, column))

                temp_user_db_session.add(new_profile)

            for card in user_subscripting_cards:
                new_card = CardTable()

                target_columns = (
                    'uuid', 'profile_id',
                    'name', 'data', 'preview_url',
                    'commit_id', 'created_at', 'modified_at',
                    'deleted_at', 'why_deleted')

                for column in target_columns:
                    setattr(new_card, column, getattr(card, column))

                temp_user_db_session.add(new_card)

            for card_relation in user_card_relations:
                new_card_subscription = CardTable()

                target_columns = (
                    'uuid', 'profile_id', 'card_id',
                    'commit_id', 'created_at')

                for column in target_columns:
                    setattr(new_card_subscription, column, getattr(card_relation, column))

                temp_user_db_session.add(new_card_subscription)

        temp_user_db_session.commit()
        temp_user_db_engine.dispose()  # Disconnect all connections (for safety)

        temp_user_db_file_pt = pt.Path(temp_user_db_file.name)

        with temp_user_db_file_pt.open('rb') as fp:
            s3_client = boto3.client('s3', region_name=flask.current_app.config.get('AWS_REGION'))
            s3_client.upload_fileobj(fp,
                                     flask.current_app.config.get('AWS_S3_BUCKET_NAME'),
                                     f'user_db/{user_id}/sync_db.sqlite')
        return temp_user_db_file
    except Exception as err:
        print(utils.get_traceback_msg(err))
        # TODO: Do something proper while creating and uploading user db file
        print('Exception raised while creating user sqlite file')
        return None


def get_user_db(user_id: int) -> typing.Union[typing.IO[bytes], io.BytesIO]:
    bucket_name = flask.current_app.config.get('AWS_S3_BUCKET_NAME')
    s3 = boto3.client('s3', region_name=flask.current_app.config.get('AWS_REGION'))
    temp_db_file: io.BytesIO = io.BytesIO()
    try:
        s3.download_fileobj(bucket_name, f'user_db/{user_id}/sync_db.sqlite', temp_db_file)
        temp_db_file.seek(0)
        return temp_db_file
    except botocore.client.ClientError as err:
        if utils.safe_int(err.response['Error']['Code']) == 404:
            new_db_file = create_user_db(user_id)
            if new_db_file:
                return new_db_file
        raise err


def get_user_db_md5(user_id: int) -> str:
    try:
        bucket_name = flask.current_app.config.get('AWS_S3_BUCKET_NAME')
        s3 = boto3.client('s3', region_name=flask.current_app.config.get('AWS_REGION'))
        return s3.head_object(
            Bucket=bucket_name,
            Key=f'user_db/{user_id}/sync_db.sqlite'
        )['ETag'][1:-1]
    except botocore.client.ClientError as err:
        if utils.safe_int(err.response['Error']['Code']) == 404:
            new_db_file = create_user_db(user_id)
            if new_db_file:
                file_md5 = utils.fileobj_md5(new_db_file)
                new_db_file.close()
                return file_md5
        return ''
    except Exception:
        return ''


def check_user_db_md5(user_id: int, md5hash: str) -> bool:
    '''
    This function will check argument "md5hash" to MD5 hash of user's db file on S3.
    Note that S3's ETag may or may not be an MD5 digest of the object's content data,
    but we won't use Multipart Upload or Encryption, so it'll be fine,
    unless AWS changes their rules.
    See: https://docs.aws.amazon.com/AmazonS3/latest/API/RESTCommonResponseHeaders.html
    '''
    return get_user_db_md5(user_id) == md5hash


def delete_user_db(user_id: int) -> None:
    try:
        bucket_name = flask.current_app.config.get('AWS_S3_BUCKET_NAME')
        s3 = boto3.client('s3', region_name=flask.current_app.config.get('AWS_REGION'))
        s3.delete_object(
            Bucket=bucket_name,
            Key=f'user_db/{user_id}/sync_db.sqlite')
    except botocore.client.ClientError as err:
        if utils.safe_int(err.response['Error']['Code']) == 404:
            return
        raise err
    except Exception as err:
        raise err
