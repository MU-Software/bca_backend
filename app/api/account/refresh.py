import flask
import flask.views
import jwt
import jwt.exceptions

import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module

from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db


class AccessTokenIssueRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={
            'User-Agent': {'type': 'string', },
            'X-Csrf-Token': {'type': 'string', },
        },
        optional_fields={'X-Client-Token': {'type': 'string', }, },
        auth={api_class.AuthType.RefreshToken: True, })
    def post(self, req_header: dict, refresh_token: jwt_module.RefreshToken):
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
            response_header, response_body = jwt_module.refresh_login_data(
                                                refresh_token_cookie,
                                                req_header.get('User-Agent'),
                                                req_header.get('X-Csrf-Token'),
                                                req_header.get('X-Client-Token', None),
                                                flask.request.remote_addr,
                                                flask.current_app.config.get('SECRET_KEY'))
        except jwt.exceptions.ExpiredSignatureError:
            return AccountResponseCase.refresh_token_expired.create_response()
        except Exception:
            return AccountResponseCase.refresh_token_invalid.create_response()

        return AccountResponseCase.access_token_refreshed.create_response(
                    header=response_header,
                    data=response_body)
