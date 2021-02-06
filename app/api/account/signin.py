import flask
import flask.views

import app.api as api
import app.database as db_module
import app.database.user as user
import app.database.jwt as jwt_module
import app.common.decorator as deco_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db


class SignInRoute(flask.views.MethodView):
    @deco_module.PERMISSION(deco_module.need_signed_out)
    def post(self):
        # { 'id' : '', 'pw' : '' }

        # TODO: Remove previous token and issue new token when client environment is same
        try:
            login_req = flask.request.get_json(force=True)
            login_req = {k: v for k, v in login_req.items() if v}

            required_fields = ['id', 'pw']
            if (not all([z in login_req.keys() for z in required_fields])) or (not all(list(login_req.values()))):
                return api.create_response(
                    code=400, success=False,
                    message='ID or Password omitted')
        except Exception:
            return api.create_response(
                code=400, success=False,
                message='Wrong request body data - JSON decode failed')

        account_result, reason = user.User.try_login(login_req['id'], login_req['pw'])

        if account_result is False:
            if reason == 'ACCOUNT_NOT_FOUND':
                return AccountResponseCase.user_not_found.create_response()
            elif reason == 'WRONG_PASSWORD':
                return AccountResponseCase.user_wrong_password.create_response()
            elif 'TOO_MUCH_LOGIN_FAIL' in reason:
                return AccountResponseCase.user_locked.create_response(
                            data={'reason': 'Too many login attempts'})
            elif reason.startswith('ACCOUNT_LOCKED'):
                return AccountResponseCase.user_locked.create_response(
                            data={'reason': reason.replace('ACCOUNT_LOCKED::', '')})
            elif reason.startswith('ACCOUNT_DEACTIVATED'):
                return AccountResponseCase.user_deactivated.create_response(
                            data={'reason': reason.replace('ACCOUNT_DEACTIVATED::', '')})
            elif reason == 'DB_ERROR':
                return CommonResponseCase.db_error.create_response()
            return CommonResponseCase.server_error.create_response()

        refresh_token_cookie,\
            access_token_cookie,\
            refresh_token_data,\
            access_token_data = jwt_module.create_login_cookie(
                                            account_result,
                                            flask.current_app.config.get('SECRET_KEY'))

        return AccountResponseCase.user_signed_in.create_response(
                    data={
                        'RefreshToken': refresh_token_data,
                        'AccessToken': access_token_data,
                    }, header=(
                        ('Set-Cookie', refresh_token_cookie),
                        ('Set-Cookie', access_token_cookie),
                    ))
