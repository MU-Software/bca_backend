import datetime
import flask
import flask.views
import jwt
import typing

import app.api.helper_class as api_class
import app.common.utils as utils
import app.database as db_module
import app.database.jwt as jwt_module

from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db


class AccessTokenIssueRoute(flask.views.MethodView, api_class.MethodViewMixin):
    def post(self):
        '''
        description: Re-issue old tokens(access, refresh)
        responses:
            - user_not_signed_in
            - refresh_token_expired
            - refresh_token_invalid
            - access_token_refreshed
        '''
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

        response_header: list[tuple[str]] = list()
        response_data: dict[str, typing.Any] = dict()

        # Access token can always be re-issued
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
        response_header.append(('Set-Cookie', access_token_cookie))
        response_data['AccessToken'] = access_token_data

        # Refresh token will be re-issued only when there's 10 days left until token expires
        token_exp_time = refresh_token.exp.replace(tzinfo=utils.UTC)
        if token_exp_time < datetime.datetime.utcnow().replace(tzinfo=utils.UTC) + datetime.timedelta(days=10):
            try:
                # Re-issue refresh token
                refresh_token.exp = datetime.datetime.utcnow().replace(microsecond=0)  # Drop microseconds
                refresh_token.exp += jwt_module.refresh_token_valid_duration
                db.session.commit()

                response_header.append(('Set-Cookie', refresh_token.create_token()))
                response_data['AccessToken'] = {
                    'exp': refresh_token.exp
                }
            except Exception:
                pass

        return AccountResponseCase.access_token_refreshed.create_response(
                    header=response_header, data=response_data)
