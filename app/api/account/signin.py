import flask
import flask.views

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.user as user
import app.database.jwt as jwt_module
import app.common.decorator as deco_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db


class SignInRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @deco_module.PERMISSION(deco_module.need_signed_out)
    def post(self):
        # { 'id' : '', 'pw' : '' }
        login_req = utils.request_body(required_fields=['id', 'pw'])

        if type(login_req) == list:
            return CommonResponseCase.body_required_omitted.create_response(data={'lacks': login_req})
        elif login_req is None:
            return CommonResponseCase.body_invalid.create_response()
        elif not login_req:
            return CommonResponseCase.body_empty.create_response()
        elif type(login_req) != dict:
            return CommonResponseCase.body_invalid.create_response()

        if 'User-Agent' not in flask.request.headers:
            return CommonResponseCase.header_required_omitted.create_response(data={'lacks': 'User-Agent'})

        account_result, reason = user.User.try_login(login_req['id'], login_req['pw'])

        if account_result is False:
            if reason == 'ACCOUNT_NOT_FOUND':
                return AccountResponseCase.user_not_found.create_response()
            elif reason.startswith('WRONG_PASSWORD'):
                return AccountResponseCase.user_wrong_password.create_response(
                    data={'left_chance': int(reason.replace('WRONG_PASSWORD::', ''))}
                )
            elif 'TOO_MUCH_LOGIN_FAIL' in reason:
                return AccountResponseCase.user_locked.create_response(
                            data={'reason': 'TOO_MUCH_LOGIN_FAIL'})
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
                                            flask.request.headers.get('User-Agent'),
                                            flask.request.headers.get('Client-Token', None),
                                            flask.request.remote_addr,
                                            flask.current_app.config.get('SECRET_KEY'))

        return AccountResponseCase.user_signed_in.create_response(
                    data={
                        'email': account_result.email,
                        'id': account_result.id,
                        'nick': account_result.nickname,
                        'uuid': account_result.uuid,

                        'RefreshToken': refresh_token_data,
                        'AccessToken': access_token_data,
                    }, header=(
                        ('Set-Cookie', refresh_token_cookie),
                        ('Set-Cookie', access_token_cookie),
                    ))
