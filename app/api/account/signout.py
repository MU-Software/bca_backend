import datetime
import flask
import flask.views

import app.api.helper_class as api_class
import app.common.utils as utils
import app.database as db_module
import app.database.jwt as jwt_module

from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db


class SignOutRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestBody(
        required_fields={'signout': {'type': 'string', }, })
    def post(self, req_body):
        '''
        description: Sign-Out and expire user token
        responses:
            - user_signed_out
        '''
        server_name = flask.current_app.config.get('SERVER_NAME')
        restapi_version = flask.current_app.config.get('RESTAPI_VERSION')

        refresh_token_remover_cookie = utils.delete_cookie(
                                            name='refresh_token',
                                            path=f'/api/{restapi_version}/account',
                                            domain=server_name if restapi_version != 'dev' else None,
                                            samesite='None' if restapi_version == 'dev' else 'strict',
                                            secure=True)
        access_token_remover_cookie = utils.delete_cookie(
                                            name='access_token',
                                            path='/',
                                            domain=server_name if restapi_version != 'dev' else None,
                                            samesite='None' if restapi_version == 'dev' else 'strict',
                                            secure=True)
        refresh_token_remover_header = ('Set-Cookie', refresh_token_remover_cookie)
        access_token_remover_header = ('Set-Cookie', access_token_remover_cookie)

        # TODO: Revoke access token by setting jti to redis DB
        refresh_token_cookie = flask.request.cookies.get('refresh_token', '')
        if refresh_token_cookie:
            try:
                refresh_token = jwt_module.RefreshToken.from_token(
                                    refresh_token_cookie,
                                    flask.current_app.config.get('SECRET_KEY'))
            except Exception:
                return AccountResponseCase.user_signed_out.create_response()

            revoke_target_jti = refresh_token.jti
            print(f'Refresh token {revoke_target_jti} removed!')
            try:
                db.session.delete(refresh_token)
                db.session.commit()
            except Exception:
                print('Raised error while removing token from DB')

            try:
                redis_db.set('refresh_revoke=' + str(revoke_target_jti), 'revoked', datetime.timedelta(weeks=2))
            except Exception:
                print('Raised error while removing token from REDIS')

            return AccountResponseCase.user_signed_out.create_response(
                header=(refresh_token_remover_header, access_token_remover_header),
                data={'OK': 'Goodbye!'})

        return AccountResponseCase.user_signed_out.create_response(
            header=(refresh_token_remover_header, access_token_remover_header),
            data={'Warning': 'User already signed-out'})
