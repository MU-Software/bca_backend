import datetime
import flask
import inspect
import jwt
import redis
import typing

import app.common.utils as utils
import app.database as db_module
import app.database.user as user_module

db = db_module.db
redis_db: redis.StrictRedis = db_module.redis_db

# Refresh token will expire after 30 days
refresh_token_valid_duration: datetime.timedelta = datetime.timedelta(days=30)
# Access token will expire after 1 hour
access_token_valid_duration: datetime.timedelta = datetime.timedelta(hours=1)

allowed_claim_in_jwt: list[str] = ['api_ver', 'iss', 'exp', 'user', 'sub', 'jti', 'role']


class TokenBase:
    # This will raise error when env var "RESTAPI_VERSION" not set.
    api_ver: str = flask.current_app.config.get('RESTAPI_VERSION')

    # Registered Claim
    iss: str = flask.current_app.config.get('SERVER_NAME')  # Token Issuer(Fixed)
    exp: datetime.datetime = None  # Expiration Unix Time
    sub: str = ''  # Token name
    jti: int = -1  # JWT token ID

    # We won't use public claim yet
    # domain: str = ''

    # Private Claim
    user: int = -1  # Audience, User, Token holder
    # data: dict
    role: str = ''

    def create_token(self, key: str, algorithm: str = 'HS256', exp_reset: bool = False) -> str:
        if not self.sub:
            raise jwt.exceptions.MissingRequiredClaimError('Subject not set in JWT class')
        if self.user and type(self.user) == int and self.user < 0:
            raise jwt.exceptions.MissingRequiredClaimError('Audience not set in JWT class')
        if self.jti and type(self.jti) == int and self.jti < 0:
            raise jwt.exceptions.MissingRequiredClaimError('Token ID not set in JWT class')

        if exp_reset:
            self.exp = datetime.datetime.utcnow().replace(microsecond=0)  # Drop microseconds
            self.exp += refresh_token_valid_duration
        else:
            current_time = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)

            if type(self.exp) == int:
                token_exp_time = datetime.datetime.fromtimestamp(self.exp, utils.UTC)
            else:
                if self.exp:
                    token_exp_time = self.exp.replace(tzinfo=utils.UTC)
                else:
                    token_exp_time = None

            if (not token_exp_time) or (token_exp_time < current_time):
                raise jwt.exceptions.ExpiredSignatureError('Token has reached expiration time')

        result_payload = dict()
        attrs = inspect.getmembers(self, lambda o: not callable(o))

        for attr_name, attr_value in attrs:
            if attr_name in allowed_claim_in_jwt:
                result_payload[attr_name] = attr_value

        return jwt.encode(payload=result_payload, key=key, algorithm=algorithm)

    @classmethod
    def from_token(cls, jwt_input: str, key: str, algorithm: str = 'HS256') -> 'TokenBase':
        token_data = jwt.decode(jwt_input, key=key, algorithms=algorithm)

        current_api_ver: str = flask.current_app.config.get('RESTAPI_VERSION')
        if token_data.get('api_ver', '') != current_api_ver:
            raise jwt.exceptions.InvalidTokenError('Token api version mismatch')
        if token_data.get('sub', '') != cls.sub:
            raise jwt.exceptions.InvalidTokenError('Token sub mismatch')

        token_exp_time = token_data.get('exp', 0)
        if type(token_exp_time) == int:
            if not token_exp_time:
                raise jwt.exceptions.ExpiredSignatureError('No expiration date included')
            token_exp_time = datetime.datetime.fromtimestamp(token_exp_time, utils.UTC)
        elif type(token_exp_time) == datetime.datetime:
            token_exp_time = token_exp_time.replace(tzinfo=utils.UTC)
        else:
            raise jwt.exceptions.InvalidTokenError('Expiration date could not be parsed')

        if token_exp_time < datetime.datetime.utcnow().replace(tzinfo=utils.UTC):
            raise jwt.exceptions.ExpiredSignatureError('Token has reached expiration time')
        token_data['exp'] = token_exp_time

        # Filter and rebuild token data so that only allowed claim is in token
        token_data = {k: token_data[k] for k in token_data if k in allowed_claim_in_jwt}

        new_token = cls()
        new_token.__dict__.update(token_data)
        return new_token


class AccessToken(TokenBase):
    # Registered Claim
    sub: str = 'Access'

    _refresh_token: 'RefreshToken' = None

    def create_token(self, key: str, algorithm: str = 'HS256', exp_reset: bool = False) -> str:
        if not RefreshToken.query.filter(RefreshToken.jti == self.jti).first():
            raise Exception('Access Token could not be issued')

        new_token = super().create_token(key, algorithm=algorithm, exp_reset=exp_reset)

        # If new token safely issued, then remove revoked history
        redis_result = redis_db.hget('refresh_revoke', str(self.jti))
        if redis_result and redis_result == b'revoked':
            redis_db.hdel('refresh_revoke', str(self.jti))

        return new_token

    @classmethod
    def from_token(cls, jwt_input: str, key: str, algorithm: str = 'HS256') -> 'AccessToken':
        parsed_token = super().from_token(jwt_input, key, algorithm)

        # Check if token's revoked
        redis_result = redis_db.hget('refresh_revoke', str(parsed_token.jti))
        if redis_result and redis_result == b'revoked':
            redis_db.hdel('refresh_revoke', str(parsed_token.jti))
            raise jwt.exceptions.InvalidTokenError('This token was revoked')

        return parsed_token

    @classmethod
    def from_refresh_token(cls, refresh_token: 'RefreshToken'):
        # Check refresh token exp
        current_time = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)

        if type(refresh_token.exp) == int:
            token_exp_time = datetime.datetime.fromtimestamp(refresh_token.exp, utils.UTC)
        else:
            if refresh_token.exp:
                token_exp_time = refresh_token.exp.replace(tzinfo=utils.UTC)
            else:
                token_exp_time = None
        if (not token_exp_time) or (token_exp_time < current_time):
            raise jwt.exceptions.ExpiredSignatureError('Refresh token has reached expiration time')

        new_token = AccessToken()
        new_token._refresh_token = refresh_token
        new_token.exp = datetime.datetime.utcnow().replace(microsecond=0)  # Drop microseconds
        new_token.exp += access_token_valid_duration
        new_token.user = refresh_token.user
        # Access token's JTI must be same with Refresh token's.
        new_token.jti = refresh_token.jti
        new_token.role = refresh_token.role

        return new_token


class RefreshToken(TokenBase, db.Model, db_module.DefaultModelMixin):
    __tablename__ = 'TB_REFRESH_TOKEN'

    # Registered Claim
    sub: str = 'Refresh'
    # Redefine fields to define SA's column on metadata
    # JWT token ID
    jti = db.Column(db_module.PrimaryKeyType,
                    db.Sequence('SQ_RefreshToken_UUID'),
                    primary_key=True)
    # Expiration Unix Time
    exp = db.Column(db.DateTime, nullable=False)
    # Audience, User, Token holder
    user = db.Column(db_module.PrimaryKeyType,
                     db.ForeignKey('TB_USER.uuid'),
                     nullable=False)
    # We need to change all refresh tokens' role when user's role is changed
    role = db.Column(db.String, nullable=True)

    # Backref
    usertable = db.relationship('User',
                                primaryjoin=user == user_module.User.uuid,
                                backref=db.backref('refresh_tokens',
                                                   order_by='RefreshToken.modified_at.desc()'))


    @classmethod
    def from_usertable(cls, userdata: user_module.User) -> 'RefreshToken':
        new_token = cls()
        new_token.usertable = userdata
        new_token.role = userdata.role
        new_token.exp = datetime.datetime.utcnow().replace(microsecond=0)  # Drop microseconds
        new_token.exp += refresh_token_valid_duration
        return new_token

    @classmethod
    def from_token(cls, jwt_input: str, key: str, algorithm: str = 'HS256') -> 'RefreshToken':
        token_data = jwt.decode(jwt_input, key=key, algorithms=algorithm)

        current_api_ver: str = flask.current_app.config.get('RESTAPI_VERSION')
        if token_data.get('api_ver', '') != current_api_ver:
            raise jwt.exceptions.InvalidTokenError('Token api version mismatch')
        if token_data.get('sub', '') != cls.sub:
            raise jwt.exceptions.InvalidTokenError('Token sub mismatch')

        # Get token using JTI, but only
        target_token = RefreshToken.query.filter(RefreshToken.jti == token_data.get('jti', -1))\
                                         .filter(RefreshToken.exp > datetime.datetime.utcnow())\
                                         .first()
        if not target_token:
            raise Exception('RefreshToken not found on DB')

        if type(target_token.exp) == int:
            target_token.exp = datetime.datetime.fromtimestamp(target_token.exp, utils.UTC)

        token_exp_time = target_token.exp.replace(tzinfo=utils.UTC)
        if token_exp_time < datetime.datetime.utcnow().replace(tzinfo=utils.UTC):
            raise jwt.exceptions.ExpiredSignatureError('Refresh token has reached expiration time')

        db_token_exp = target_token.exp.replace(tzinfo=utils.UTC)
        cookie_token_exp = datetime.datetime.fromtimestamp(token_data.get('exp', 0), utils.UTC)

        if target_token.user == int(token_data.get('user', '')) and db_token_exp == cookie_token_exp:
            return target_token
        else:
            raise Exception('RefreshToken is not valid')

    def create_token(self, key: str, algorithm: str = 'HS256', exp_reset: bool = True) -> str:
        self.exp = datetime.datetime.utcnow().replace(microsecond=0)  # Drop microseconds
        self.exp += refresh_token_valid_duration

        if self.jti and self.jti <= -1:
            self.jti = None
            db_module.db.session.add(self)

        try:
            db_module.db.session.commit()
        except Exception:
            db_module.db.session.rollback()
            raise

        return super().create_token(key, algorithm, False)


def create_login_cookie(userdata: user_module.User, key: str, algorithm: str = 'HS256') -> tuple[str, str, dict, dict]:
    secret_key = flask.current_app.config.get('SECRET_KEY')

    refresh_token = RefreshToken.from_usertable(userdata)
    refresh_token_jwt = refresh_token.create_token(secret_key)

    access_token = AccessToken.from_refresh_token(refresh_token)
    access_token_jwt = access_token.create_token(secret_key)

    refresh_token_data = {
        'exp': refresh_token.exp,
    }
    access_token_data = {
        'exp': access_token.exp,
    }

    refresh_token_cookie = utils.cookie_creator(
        name='refresh_token',
        data=refresh_token_jwt,
        path=f'/{refresh_token.api_ver}/account',
        expires=utils.cookie_datetime(refresh_token.exp),
        secure=not flask.current_app.config.get('DEBUG', False))
    access_token_cookie = utils.cookie_creator(
        name='access_token',
        data=access_token_jwt,
        path='/',
        expires=utils.cookie_datetime(access_token.exp),
        secure=not flask.current_app.config.get('DEBUG', False))

    return refresh_token_cookie, access_token_cookie, refresh_token_data, access_token_data


def get_account_data() -> typing.Union[None, bool, AccessToken]:
    '''
    return case:
        if None: Token not available
        if False: Token must be re-issued
        else: Token Object
    '''
    try:
        access_token_cookie = flask.request.cookies.get('access_token', '')
        if not access_token_cookie:
            return None

        try:
            access_token = AccessToken.from_token(
                access_token_cookie,
                flask.current_app.config.get('SECRET_KEY'))
        except jwt.exceptions.ExpiredSignatureError:
            return False
        except jwt.exceptions.InvalidTokenError as err:
            if err.message == 'This token was revoked':
                return False
            return None
        except Exception:
            return None
        if not access_token:
            return None

        return access_token
    except Exception:
        return None
