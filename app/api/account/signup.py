import datetime
import flask
import flask.views
from passlib.hash import argon2
import secrets
import sqlalchemy as sql
import jwt

import app.api as api
import app.common.utils as utils
import app.common.mailgun as mailgun
import app.database as db_module
import app.database.user as user
import app.database.jwt as jwt_module
import app.common.decorator as deco_module

import app.api.response_case as common_resp
import app.api.account.response_case as account_resp

db = db_module.db

# SignUp confirmation email will expire after 7 days
signup_verify_mail_valid_duration: datetime.timedelta = datetime.timedelta(days=7)


class SignUpRoute(flask.views.MethodView):
    @deco_module.PERMISSION(deco_module.need_signed_out)
    def post(self):
        try:
            new_user_req = flask.request.get_json(force=True)
            new_user_req = {k: v for k, v in new_user_req.items() if v}
        except Exception:
            return common_resp.CommonResponseCase.body_invalid.create_response()

        # At least we need those values.
        must_require = ['id', 'pw', 'nick', 'email']

        missing_info = [z for z in must_require if z not in new_user_req]
        if missing_info:
            return common_resp.CommonResponseCase.body_required_omitted.create_response(
                data={'lacks': missing_info}
            )

        # Allow only those columns so that user cannot change important values.
        new_user_info_keys = ['id', 'pw', 'nick', 'email', 'description']
        unwanted_keys = set(list(new_user_req.keys())) - set(new_user_info_keys)
        for unwanted in unwanted_keys:
            new_user_req.pop(unwanted)

        new_user_pw = new_user_req.pop('pw')

        new_user = user.User()
        new_user.email = new_user_req['email']
        new_user.id = new_user_req['id']
        new_user.nickname = new_user_req['nick']
        new_user.description = None if not new_user_req.get('description', '') else new_user_req['description']
        new_user.password = argon2.hash(new_user_pw)
        new_user.pw_changed_at = sql.func.now()
        new_user.last_login_date = sql.func.now()
        db.session.add(new_user)

        try:
            db.session.commit()

            # Send account verification & confirmation mail
            email_token = jwt.encode({
                'api_ver': flask.current_app.config.get('RESTAPI_VERSION'),
                'iss': flask.current_app.config.get('SERVER_NAME'),
                'exp': datetime.datetime.utcnow().replace(tzinfo=utils.UTC) + signup_verify_mail_valid_duration,
                'sub': 'Email Auth',
                'jti':  secrets.randbits(64),
                'user': new_user.uuid,
                'data': {
                    'action': 'EMAIL_VERIFY'
                },
            }, key=flask.current_app.config.get('SECRET_KEY'), algorithm='HS256')
            new_user.email_secret = email_token

            db.session.commit()
        except Exception as err:
            try:
                err_diag = db_module.IntegrityCaser(err)
                if err_diag[0] == 'FAILED_UNIQUE':
                    return api.create_response(
                        code=401, success=False,
                        message=f'"{err_diag[1]}" is already in use')
                else:
                    raise err
            except Exception:
                print(str(err))
                return api.create_response(
                    code=500, success=False,
                    message='Unknown error occured while registering new user')

        try:
            email_result = flask.render_template(
                'email/email_verify.html',
                domain_url=flask.current_app.config.get('SERVER_NAME', 'http://localhost:5000'),
                project_name=flask.current_app.config.get('PROJECT_NAME'),
                user_nick=new_user.nickname,
                email_key=email_token,
                language='kor'
            )
            mailgun.gmail_send_mail(
                'musoftware@mudev.cc',
                new_user.email,
                'DEVCO에 오신 것을 환영합니다!',
                email_result)
        except Exception as err:
            import traceback
            print(''.join(traceback.format_exception(etype=type(err), value=err, tb=err.__traceback__)))
            print('Error raised while sending user email verification mail')

        refresh_token_cookie,\
            access_token_cookie,\
            refresh_token_data,\
            access_token_data = jwt_module.create_login_cookie(
                                            new_user,
                                            flask.current_app.config.get('SECRET_KEY'))

        return api.create_response(
            code=201, success=True,
            message='',
            header=(
                ('Set-Cookie', refresh_token_cookie),
                ('Set-Cookie', access_token_cookie),
            ),
            data={
                'RefreshToken': refresh_token_data,
                'AccessToken': access_token_data,
            })
