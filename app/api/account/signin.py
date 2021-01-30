import flask
import flask.views
import app.api as api
import app.database as db_module
import app.database.user as user
import app.database.jwt as jwt_module
import app.common.decorator as deco_module

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
            code = 500
            message = 'Server error'
            if reason == 'ACCOUNT_NOT_FOUND':
                code, message = 401, 'Account not found'
            elif reason == 'WRONG_PASSWORD':
                code, message = 401, 'Password mismatch'
            elif 'TOO_MUCH_LOGIN_FAIL' in reason:
                code, message = 401, 'Account locked = Too many login attempts'
            elif reason.startswith('ACCOUNT_LOCKED'):
                code, message = 401, reason.replace('ACCOUNT_LOCKED::', '')
            elif reason.startswith('ACCOUNT_DEACTIVATED'):
                code, message = 401, reason.replace('ACCOUNT_DEACTIVATED::', '')
            elif reason == 'DB_ERROR':
                code, message = 500, 'Server error'

            return api.create_response(
                code=code, success=False,
                message=message)

        refresh_token_cookie,\
            access_token_cookie,\
            refresh_token_data,\
            access_token_data = jwt_module.create_login_cookie(
                                            account_result,
                                            flask.current_app.config.get('SECRET_KEY'))

        return api.create_response(
            code=200, success=True,
            message='',
            header=(
                ('Set-Cookie', refresh_token_cookie),
                ('Set-Cookie', access_token_cookie),
            ),
            data={
                'RefreshToken': refresh_token_data,
                'AccessToken': access_token_data,
            })
