import boto3
import botocore.client
import flask
import io
import sqlalchemy as sql
import sqlalchemy.ext.declarative as sqldec
import sqlalchemy.orm as sqlorm
import tempfile
import typing

import app.common.utils as utils
import app.database.profile as profile_module
import app.bca.database.user_db_table as bca_user_db_table


def create_user_db(user_id: int,
                   insert_all_data_from_global_db: bool = False,
                   delete_if_available: bool = False) -> typing.Optional[tempfile.IO[bytes]]:
    # bca: create user's db file and upload to s3
    try:
        if delete_if_available:
            delete_user_db(user_id)

        # Create temporary file and connection
        temp_user_db_file = tempfile.NamedTemporaryFile('w+b', delete=True)

        temp_user_db_engine = sql.create_engine(f'sqlite://{temp_user_db_file.name}')
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
            user_profiles_query = profile_module.Profile.query\
                .filter(profile_module.Profile.locked_at != None)\
                .filter(profile_module.Profile.deleted_at != None)\
                .filter(profile_module.Profile.user_id == user_id)\
                .subquery()  # noqa

            user_card_relations_query = profile_module.CardSubscribed.query\
                .filter(profile_module.CardSubscribed.profile_id.in_(user_profiles_query))

            user_subscripting_cards_query = user_card_relations_query\
                .group_by(profile_module.CardSubscribed.card_id)\
                .join(profile_module.CardSubscribed.card)\
                .options(sqlorm.contains_eager(profile_module.CardSubscribed.card))\
                .filter(profile_module.Card.locked_at != None)  # noqa

            user_following_profiles_query = user_card_relations_query\
                .group_by(profile_module.CardSubscribed.profile_id)\
                .join(profile_module.CardSubscribed.profile_id)\
                .options(sqlorm.contains_eager(profile_module.CardSubscribed.profile))\
                .filter(profile_module.Profile.locked_at != None)  # noqa

            user_card_relations: list[profile_module.CardSubscribed] = user_card_relations_query.all()
            user_subscripting_cards: list[profile_module.CardSubscribed] = user_subscripting_cards_query.all()
            user_following_profiles: list[profile_module.CardSubscribed] = user_following_profiles_query.all()

            for profile in user_following_profiles:
                new_profile = ProfileTable()
                queried_profile = profile.profile

                target_columns = (
                    'uuid', 'description', 'data',
                    'name', 'email', 'phone', 'sns',
                    'commit_id', 'created_at', 'modified_at',
                    'deleted_at', 'why_deleted',
                    'guestbook', 'announcement', 'private')

                for column in target_columns:
                    setattr(new_profile, column, getattr(queried_profile, column))

                temp_user_db_session.add(new_profile)

            for card in user_subscripting_cards:
                new_card = CardTable()
                queried_card = card.card

                target_columns = (
                    'uuid', 'profile_id',
                    'name', 'data', 'preview_url',
                    'commit_id', 'created_at', 'modified_at',
                    'deleted_at', 'why_deleted')

                for column in target_columns:
                    setattr(new_card, column, getattr(queried_card, column))

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
        temp_user_db_file.seek(0)

        s3_client = boto3.client('s3', region_name=flask.current_app.config.get('AWS_REGION'))
        s3_client.upload_fileobj(temp_user_db_file,
                                 flask.current_app.config.get('AWS_S3_BUCKET_NAME'),
                                 f'/user_db/{user_id}/sync_db.sqlite')
        return temp_user_db_file
    except Exception:
        # TODO: Do something proper while creating and uploading user db file
        print('Exception raised while creating user sqlite file')
        return None


def get_user_db(user_id: int) -> typing.Union[tempfile.IO[bytes], io.BytesIO]:
    bucket_name = flask.current_app.config.get('AWS_S3_BUCKET_NAME')
    s3 = boto3.client('s3', region_name=flask.current_app.config.get('AWS_REGION'))
    temp_db_file: io.BytesIO = io.BytesIO()
    try:
        s3.download_fileobj(bucket_name, f'/user_db/{user_id}/sync_db.sqlite', temp_db_file)
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
            Key=f'/user_db/{user_id}/sync_db.sqlite'
        )['ETag'][1:-1]
    except botocore.client.ClientError as err:
        if utils.safe_int(err.response['Error']['Code']) == 404:
            new_db_file = create_user_db(user_id)
            if new_db_file:
                return utils.fileobj_md5(new_db_file)
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
            Key=f'/user_db/{user_id}/sync_db.sqlite')
    except botocore.client.ClientError as err:
        if utils.safe_int(err.response['Error']['Code']) == 404:
            return
        raise err
    except Exception as err:
        raise err
