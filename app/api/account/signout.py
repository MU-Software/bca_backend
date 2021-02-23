import flask
import flask.views

import app.api as api
import app.common.utils as utils
import app.database as db_module
import app.database.jwt as jwt_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db


class SignOutRoute(flask.views.MethodView, api.MethodViewMixin):
    def post(self):
        # Check POST data so that someone "accidently" make user signing out
        try:
            signout_req = flask.request.get_json(force=True)
            signout_req = {k: v for k, v in signout_req.items() if v}
        except Exception:
            return CommonResponseCase.body_invalid.create_response()

        if 'signout' not in signout_req:
            return CommonResponseCase.body_required_omitted.create_response(
                data={'lacks': ['signout']}
            )

        refresh_token_remover_cookie = utils.delete_cookie(
                                            name='refresh_token',
                                            path=f'/api/{api.restapi_version}/account',
                                            domain=api.server_name if api.restapi_version != 'dev' else None,
                                            samesite='None' if api.restapi_version == 'dev' else 'strict',
                                            secure=True)
        access_token_remover_cookie = utils.delete_cookie(
                                            name='access_token',
                                            path='/',
                                            domain=api.server_name if api.restapi_version != 'dev' else None,
                                            samesite='None' if api.restapi_version == 'dev' else 'strict',
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

            return AccountResponseCase.user_signed_out.create_response(
                header=(refresh_token_remover_header, access_token_remover_header),
                data={'OK': 'Goodbye!'})

        return AccountResponseCase.user_signed_out.create_response(
            header=(refresh_token_remover_header, access_token_remover_header),
            data={'Warning': 'User already signed-out'})
