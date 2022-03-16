import datetime
import sqlalchemy as sql
import sqlalchemy.types as sqltypes
import sqlalchemy.ext.declarative as sqldec


class UserDBDateTime(sqltypes.TypeDecorator):
    impl = sqltypes.Integer

    # Python Object to DB
    def process_bind_param(self, value: datetime.datetime, dialect):
        if value is not None:
            if isinstance(value, str):
                # Try to parse RFC1123 format time string
                time_format = '%a, %d %b %Y %H:%M:%S GMT'
                value = datetime.datetime.strptime(value, time_format).replace(tzinfo=datetime.timezone.utc)
            elif isinstance(value, (int, float)):
                # Treat value as timestamp integer
                return int(value)

            # value must be a datetime.datetime object.
            value = int(value.timestamp())
        return value

    # DB to Python Object
    def process_result_value(self, value: int, dialect):
        if value is not None:
            value = datetime.datetime.fromtimestamp(value)
        return value

    def process_literal_value(self, value, dialect):
        return super().process_result_value(value, dialect)


class UserDBBoolean(sqltypes.TypeDecorator):
    impl = sqltypes.Integer

    # Python Object to DB
    def process_bind_param(self, value: bool, dialect):
        if value is not None:
            value = int(value)
        return value

    # DB to Python Object
    def process_result_value(self, value: int, dialect):
        if value is not None:
            value = bool(value)
        return value

    def process_literal_value(self, value, dialect):
        return super().process_result_value(value, dialect)


class Profile:
    __tablename__ = 'TB_PROFILE'
    __table_args__ = {
        'sqlite_autoincrement': True,
    }

    column_names = [
        'uuid',
        'name', 'team_name', 'description', 'data', 'image_url',
        'email', 'phone', 'sns', 'address', 'private',
        'commit_id', 'created_at', 'modified_at', 'deleted_at', 'why_deleted',
    ]

    uuid = sql.Column(sql.Integer, primary_key=True, nullable=False)

    name = sql.Column(sql.TEXT, nullable=False)  # Profile name shown in list or card
    team_name = sql.Column(sql.TEXT, nullable=True)  # Profile's included organization name
    description = sql.Column(sql.TEXT, nullable=True)  # Profile description
    data = sql.Column(sql.TEXT, nullable=False)  # Profile data (in json)
    image_url = sql.Column(sql.TEXT, nullable=True)  # Profile image URL

    email = sql.Column(sql.TEXT, nullable=True)  # Main email of Profile
    phone = sql.Column(sql.TEXT, nullable=True)  # Main phone of Profile
    sns = sql.Column(sql.TEXT, nullable=True)  # Main SNS Account of profile
    address = sql.Column(sql.TEXT, nullable=True)  # Main address of profile

    commit_id = sql.Column(sql.TEXT, nullable=False)
    created_at = sql.Column(UserDBDateTime, nullable=False)
    modified_at = sql.Column(UserDBDateTime, nullable=False)
    deleted_at = sql.Column(UserDBDateTime, nullable=True)
    why_deleted = sql.Column(sql.TEXT, nullable=True)

    private = sql.Column(UserDBBoolean, nullable=False, default=0)


class ProfileRelation:
    __tablename__ = 'TB_PROFILE_RELATION'
    __table_args__ = {
        'sqlite_autoincrement': True,
    }

    column_names = [
        'uuid',
        'from_profile_id', 'to_profile_id', 'status',
        'commit_id', 'created_at', 'modified_at',
    ]

    uuid = sql.Column(sql.Integer, primary_key=True, nullable=False)

    commit_id = sql.Column(sql.TEXT, nullable=False)
    created_at = sql.Column(UserDBDateTime, nullable=False)
    modified_at = sql.Column(UserDBDateTime, nullable=False)

    status = sql.Column(sql.Integer, nullable=False, default=1)

    @sqldec.declared_attr
    def from_profile_id(cls):
        return sql.Column(sql.Integer, sql.ForeignKey('TB_PROFILE.uuid'), nullable=False)

    @sqldec.declared_attr
    def to_profile_id(cls):
        return sql.Column(sql.Integer, sql.ForeignKey('TB_PROFILE.uuid'), nullable=False)


class Card:
    __tablename__ = 'TB_CARD'
    __table_args__ = {
        'sqlite_autoincrement': True,
    }

    column_names = [
        'uuid',
        'name', 'data', 'preview_url', 'private', 'profile_id',
        'commit_id', 'created_at', 'modified_at', 'deleted_at', 'why_deleted',
    ]

    uuid = sql.Column(sql.Integer, primary_key=True, nullable=False)

    name = sql.Column(sql.TEXT, nullable=False)
    data = sql.Column(sql.TEXT, nullable=False)
    preview_url = sql.Column(sql.TEXT, nullable=False, unique=True)

    commit_id = sql.Column(sql.TEXT, nullable=False)
    created_at = sql.Column(UserDBDateTime, nullable=False)
    modified_at = sql.Column(UserDBDateTime, nullable=False)
    deleted_at = sql.Column(UserDBDateTime, nullable=True)
    why_deleted = sql.Column(sql.TEXT, nullable=True)

    private = sql.Column(UserDBBoolean, nullable=False, default=0)

    @sqldec.declared_attr
    def profile_id(cls):
        return sql.Column(sql.Integer, sql.ForeignKey('TB_PROFILE.uuid'), nullable=False)


class CardSubscription:
    __tablename__ = 'TB_CARD_SUBSCRIPTION'
    __table_args__ = {
        'sqlite_autoincrement': True,
    }

    column_names = [
        'uuid',
        'card_profile_id', 'card_id', 'subscribed_profile_id',
        'commit_id', 'created_at', 'modified_at',
    ]

    uuid = sql.Column(sql.Integer, primary_key=True, nullable=False)

    commit_id = sql.Column(sql.TEXT, nullable=False)
    created_at = sql.Column(UserDBDateTime, nullable=False)
    modified_at = sql.Column(UserDBDateTime, nullable=False)

    @sqldec.declared_attr
    def card_profile_id(cls):
        return sql.Column(sql.Integer, sql.ForeignKey('TB_PROFILE.uuid'), nullable=False)

    @sqldec.declared_attr
    def card_id(cls):
        return sql.Column(sql.Integer, sql.ForeignKey('TB_CARD.uuid'), nullable=False)

    @sqldec.declared_attr
    def subscribed_profile_id(cls):
        return sql.Column(sql.Integer, sql.ForeignKey('TB_PROFILE.uuid'), nullable=False)
