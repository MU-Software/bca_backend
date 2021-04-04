import flask
import flask.views
import jwt

import app.api.helper_class as api_class
import app.common.utils as utils
import app.database as db_module
import app.database.jwt as jwt_module

from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db


class AccessTokenIssueRoute(flask.views.MethodView, api_class.MethodViewMixin):
    def post(self):
        refresh_token_cookie = flask.request.cookies.get('refresh_token', type=str, default='')

        if not refresh_token_cookie:
            return AccountResponseCase.user_not_signed_in.create_response()

        try:
            refresh_token = jwt_module.RefreshToken.from_token(
                                refresh_token_cookie,
                                flask.current_app.config.get('SECRET_KEY'))

        except jwt.exceptions.ExpiredSignatureError:
            return AccountResponseCase.refresh_token_expired.create_response()
        except jwt.exceptions.InvalidTokenError:
            return AccountResponseCase.refresh_token_invalid.create_response()
        except Exception:
            # Unexpected thing happened while decoding login data. please re-login
            return AccountResponseCase.refresh_token_invalid.create_response()

        access_token = jwt_module.AccessToken.from_refresh_token(refresh_token)

        access_token_jwt = access_token.create_token(flask.current_app.config.get('SECRET_KEY'))
        access_token_data = {
            'exp': access_token.exp,
        }
        access_token_cookie = utils.cookie_creator(
            name='access_token',
            data=access_token_jwt,
            domain=flask.current_app.config.get('SERVER_NAME') if api_class.restapi_version != 'dev' else None,
            path='/',
            expires=utils.cookie_datetime(access_token.exp),
            samesite='None' if api_class.restapi_version == 'dev' else 'strict',
            secure=True)

        return AccountResponseCase.access_token_refreshed.create_response(
            header=(
                ('Set-Cookie', access_token_cookie),
            ),
            data={
                'AccessToken': access_token_data,
            })
