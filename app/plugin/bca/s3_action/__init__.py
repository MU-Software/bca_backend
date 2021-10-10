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
import app.database.bca.profile as profile_module
import app.plugin.bca.database.user_db_table as bca_user_db_table


def create_user_db(user_id: int,
                   insert_all_data_from_global_db: bool = False,
                   delete_if_available: bool = False) -> typing.Optional[typing.IO[bytes]]:
    # bca: create user's db file and upload to s3
    try:
        if delete_if_available:
            delete_user_db(user_id)

        # Create temporary file and connection. This only works on linux, because of NamedTemporaryFile.
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
        ProfileRelationTable = type(
            'ProfileRelationTable',
            (temp_user_db_base, bca_user_db_table.ProfileRelation),
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
        ProfileRelationTable.__table__.create(temp_user_db_engine)
        CardTable.__table__.create(temp_user_db_engine)
        CardSubscriptionTable.__table__.create(temp_user_db_engine)

        if insert_all_data_from_global_db:
            # Insert data to user db from global db
            # Find user's profiles, and find all card subscriptions using user's profiles.
            # Hopefully, we unnormalized columns, so we can query this easily... rignt?

            db = db_module.db

            # All profile's ID that created by user, following profiles, and subscribed cards' profiles
            user_profiles_query = db.session.query(profile_module.Profile.uuid)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .filter(profile_module.Profile.user_id == user_id)\
                .subquery()

            following_profiles_query = db.session.query(profile_module.ProfileRelation.to_profile_id)\
                .filter(profile_module.ProfileRelation.from_profile_id == user_id)\
                .join(profile_module.ProfileRelation.to_profile, aliased=True)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .distinct().subquery()

            subscribed_cards_profiles_query = db.session.query(profile_module.CardSubscription.card_profile_id)\
                .filter(profile_module.CardSubscription.subscribed_user_id == user_id)\
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
                .filter(profile_module.ProfileRelation.from_profile_id == user_id)\
                .join(profile_module.ProfileRelation.to_profile, aliased=True)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .distinct(profile_module.ProfileRelation.uuid).all()

            # All card subscriptions to be loaded
            card_subscriptions_query = db.session.query(profile_module.CardSubscription)\
                .filter(profile_module.CardSubscription.subscribed_user_id == user_id)\
                .join(profile_module.CardSubscription.card, aliased=True)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .distinct(profile_module.CardSubscription.uuid)

            load_target_card_subscriptions: list[profile_module.CardSubscription] = card_subscriptions_query.all()

            # All cards to be loaded
            load_target_cards: list[profile_module.Card] = db.session.query(profile_module.Card)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .filter(sql.or_(
                    profile_module.Card.user_id == user_id,  # User's cards
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
                        setattr(new_row, column, getattr(load_target_data, column))

                    temp_user_db_session.add(new_row)

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
