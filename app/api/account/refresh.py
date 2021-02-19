import flask
import flask.views
import jwt

import app.api as api
import app.common.utils as utils
import app.database as db_module
# import app.database.user as user
import app.database.jwt as jwt_module

import app.api.account.response_case as account_resp

db = db_module.db
redis_db = db_module.redis_db


class AccessTokenIssueRoute(flask.views.MethodView, api.MethodViewMixin):
    def post(self):
        refresh_token_cookie = flask.request.cookies.get('refresh_token', type=str, default='')

        if not refresh_token_cookie:
            return account_resp.AccountResponseCase.user_not_logged_in.create_response()

        try:
            refresh_token = jwt_module.RefreshToken.from_token(
                                refresh_token_cookie,
                                flask.current_app.config.get('SECRET_KEY'))

        except jwt.exceptions.ExpiredSignatureError:
            return account_resp.AccountResponseCase.refresh_token_expired.create_response()
        except jwt.exceptions.InvalidTokenError:
            return account_resp.AccountResponseCase.refresh_token_invalid.create_response()
        except Exception:
            # Unexpected thing happened while decoding login data. please re-login
            return account_resp.AccountResponseCase.refresh_token_invalid.create_response()

        access_token = jwt_module.AccessToken.from_refresh_token(refresh_token)

        access_token_jwt = access_token.create_token(flask.current_app.config.get('SECRET_KEY'))
        access_token_data = {
            'exp': access_token.exp,
        }
        access_token_cookie = utils.cookie_creator(
            name='access_token',
            data=access_token_jwt,
            path='/',
            expires=utils.cookie_datetime(access_token.exp),
            secure=not flask.current_app.config.get('DEBUG', False))

        return api.create_response(
            code=200, success=True,
            message='',
            header=(
                ('Set-Cookie', access_token_cookie),
            ),
            data={
                'AccessToken': access_token_data,
            })
