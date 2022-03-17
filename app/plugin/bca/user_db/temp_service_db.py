import enum
import os
import pathlib as pt
import typing

import sqlite3
import sqlalchemy as sql
import sqlalchemy.ext.declarative as sqldec
import sqlalchemy.orm as sqlorm

import app.plugin.bca.user_db.file_io as file_io


class TemporaryServiceDBConnection:
    engine: sql.engine.Engine = None
    session: sqlorm.scoped_session = None
    base = None
    tables: dict = None

    def __init__(self):
        # We need to change CWD because when service DB is SQLite file,
        # It places on pt.Path.cwd() / 'app' directory as that's the main API server's CWD.
        worker_cwd = pt.Path.cwd()
        apiserver_cwd = worker_cwd / 'app'
        os.chdir(apiserver_cwd)
        self.engine = sql.create_engine(os.environ.get('DB_URL'))
        os.chdir(worker_cwd)

        self.session = sqlorm.scoped_session(
                            sqlorm.sessionmaker(
                                autocommit=False,
                                autoflush=False,
                                bind=self.engine))
        self.base = sqldec.declarative_base()

        class User(self.base):
            __table__ = sql.Table(
                'TB_USER', self.base.metadata,
                autoload=True, autoload_with=self.engine)

        class RefreshToken(self.base):
            __table__ = sql.Table(
                'TB_REFRESH_TOKEN', self.base.metadata,
                autoload=True, autoload_with=self.engine)

        class Profile(self.base):
            __table__ = sql.Table(
                'TB_PROFILE', self.base.metadata,
                autoload=True, autoload_with=self.engine)

        class ProfileRelation(self.base):
            __table__ = sql.Table(
                'TB_PROFILE_RELATION', self.base.metadata,
                autoload=True, autoload_with=self.engine)

        class Card(self.base):
            __table__ = sql.Table(
                'TB_CARD', self.base.metadata,
                autoload=True, autoload_with=self.engine)

        class CardSubscribed(self.base):
            __table__ = sql.Table(
                'TB_CARD_SUBSCRIPTION', self.base.metadata,
                autoload=True, autoload_with=self.engine)

        self.tables = {
            'User': User,
            'RefreshToken': RefreshToken,
            'Profile': Profile,
            'ProfileRelation': ProfileRelation,
            'Card': Card,
            'CardSubscribed': CardSubscribed,
        }

    def get_user_fcm_tokens(self, user_id: int) -> list[str]:
        RefreshTokenTable = self.tables['RefreshToken']

        result: list[tuple[str]] = self.session.query(RefreshTokenTable.client_token)\
            .filter(RefreshTokenTable.user == int(user_id))\
            .filter(RefreshTokenTable.client_token.is_not(None))\
            .distinct().all()
        # I don't know why, I don't want to know why, I shouldn't
        # have to wonder why, but for whatever reason this stupid
        # query isn't returning list[str] correctly. (It's returning `list[tuple[str]]`)!
        # So, FCM request will fail unless we do this terribleness
        return [item for sublist in result for item in sublist]

    def insert_user_db_record(self, user_id: int, bca_sync_file: file_io.BCaSyncFile):
        temp_user_db_sqlite_conn = sqlite3.connect(bca_sync_file.pathobj)
        temp_user_db_engine = sql.create_engine('sqlite://', creator=lambda: temp_user_db_sqlite_conn)
        temp_user_db_session = sqlorm.scoped_session(
                                    sqlorm.sessionmaker(
                                        autocommit=False,
                                        autoflush=False,
                                        bind=temp_user_db_engine))
        temp_user_db_base = sqldec.declarative_base()

        # Define necessary user db tables
        class ProfileTable(temp_user_db_base):
            __table__ = sql.Table(
                'TB_PROFILE', temp_user_db_base.metadata,
                autoload=True, autoload_with=temp_user_db_engine)

        class ProfileRelationTable(temp_user_db_base):
            __table__ = sql.Table(
                'TB_PROFILE_RELATION', temp_user_db_base.metadata,
                autoload=True, autoload_with=temp_user_db_engine)

        class CardTable(temp_user_db_base):
            __table__ = sql.Table(
                'TB_CARD', temp_user_db_base.metadata,
                autoload=True, autoload_with=temp_user_db_engine)

        class CardSubscribedTable(temp_user_db_base):
            __table__ = sql.Table(
                'TB_CARD_SUBSCRIPTION', temp_user_db_base.metadata,
                autoload=True, autoload_with=temp_user_db_engine)

        # Get necessary service db tables
        TB_Profile = self.tables['Profile']
        TB_ProfileRelation = self.tables['ProfileRelation']
        TB_Card = self.tables['Card']
        TB_CardSubscription = self.tables['CardSubscribed']

        # All profile's ID that created by user, following profiles, and subscribed cards' profiles
        user_profiles_query = self.session.query(TB_Profile.uuid)\
            .filter(TB_Profile.locked_at.is_(None))\
            .filter(TB_Profile.deleted_at.is_(None))\
            .filter(TB_Profile.user_id == user_id)\
            .subquery()

        following_profiles_query = self.session.query(TB_ProfileRelation.to_profile_id)\
            .filter(TB_ProfileRelation.from_user_id == user_id)\
            .join(TB_ProfileRelation.to_profile, aliased=True)\
            .filter(TB_Profile.locked_at.is_(None))\
            .distinct().subquery()

        subscribed_cards_profiles_query = self.session.query(TB_CardSubscription.card_profile_id)\
            .filter(TB_CardSubscription.subscribed_user_id == user_id)\
            .join(TB_CardSubscription.card, aliased=True)\
            .filter(TB_Card.locked_at.is_(None))\
            .distinct().subquery()

        # All profiles to be loaded
        load_target_profiles: list[TB_Profile] = self.session.query(TB_Profile)\
            .filter(TB_Profile.locked_at.is_(None))\
            .filter(sql.or_(
                TB_Profile.uuid.in_(user_profiles_query),
                TB_Profile.uuid.in_(following_profiles_query),
                TB_Profile.uuid.in_(subscribed_cards_profiles_query),
            )).distinct(TB_Profile.uuid).all()

        # All profile relations to be loaded
        load_target_profile_relations: list[TB_ProfileRelation] = self.session.query(
            TB_ProfileRelation)\
            .filter(TB_ProfileRelation.from_user_id == user_id)\
            .join(TB_ProfileRelation.to_profile, aliased=True)\
            .filter(TB_Profile.locked_at.is_(None))\
            .distinct(TB_ProfileRelation.uuid).all()

        # All card subscriptions to be loaded
        card_subscriptions_query = self.session.query(TB_CardSubscription)\
            .filter(TB_CardSubscription.subscribed_user_id == user_id)\
            .join(TB_CardSubscription.card, aliased=True)\
            .filter(TB_Card.locked_at.is_(None))\
            .distinct(TB_CardSubscription.uuid)

        load_target_card_subscriptions: list[TB_CardSubscription] = card_subscriptions_query.all()

        # All cards to be loaded
        load_target_cards: list[TB_Card] = self.session.query(TB_Card)\
            .filter(TB_Card.locked_at.is_(None))\
            .filter(sql.or_(
                TB_Card.user_id == user_id,  # User's cards
                TB_Card.uuid.in_(  # Subscribed cards
                    card_subscriptions_query.with_entities(TB_CardSubscription.uuid)),
            ))\
            .distinct(TB_Card.uuid).all()

        load_target_table_map: list[tuple[list, typing.Type]] = [
            (load_target_profiles, ProfileTable),
            (load_target_profile_relations, ProfileRelationTable),
            (load_target_cards, CardTable),
            (load_target_card_subscriptions, CardSubscribedTable),
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
