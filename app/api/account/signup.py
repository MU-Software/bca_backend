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

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db

# SignUp confirmation email will expire after 7 days
signup_verify_mail_valid_duration: datetime.timedelta = datetime.timedelta(days=7)


class SignUpRoute(flask.views.MethodView, api.MethodViewMixin):
    @deco_module.PERMISSION(deco_module.need_signed_out)
    def post(self):
        new_user_req = utils.request_body(
            required_fields=['id', 'pw', 'nick', 'email'],
            optional_fields=['description']
        )

        if type(new_user_req) == list:
            return CommonResponseCase.body_required_omitted.create_response(data={'lacks': new_user_req})
        elif new_user_req is None:
            return CommonResponseCase.body_invalid.create_response()
        elif not new_user_req:
            return CommonResponseCase.body_empty.create_response()
        elif type(new_user_req) != dict:
            return CommonResponseCase.body_invalid.create_response()

        if 'User-Agent' not in flask.request.headers:
            return CommonResponseCase.header_required_omitted.create_response(data={'lacks': 'User-Agent'})

        # Normalize all user inputs, including password
        for k, v in new_user_req.items():
            new_user_req[k] = utils.normalize(v)

        if not utils.is_email(new_user_req['email']):
            return CommonResponseCase.body_bad_semantics.create_response(
                data={'bad_semantics': ({'email': 'WRONG'},)})
        if reason := utils.is_useridsafe(new_user_req['id']):
            return CommonResponseCase.body_bad_semantics.create_response(
                data={'bad_semantics': ({'id': reason},)})
        if reason := utils.is_passwordsafe(new_user_req['pw']):
            return CommonResponseCase.body_bad_semantics.create_response(
                data={'bad_semantics': ({'pw': reason},)})

        new_user = user.User()
        new_user.email = new_user_req['email']
        new_user.id = new_user_req['id']
        new_user.nickname = new_user_req['nick']
        new_user.description = new_user_req.get('description', None)
        new_user.password = argon2.hash(new_user_req['pw'])
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
                    return AccountResponseCase.user_already_used.create_response(data={'duplicate': dict(err_diag[1])})
                else:
                    raise err
            except Exception:
                return CommonResponseCase.server_error.create_response()

        mail_sent: bool = True
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
            mail_sent = True
        except Exception:
            mail_sent = False

        refresh_token_cookie,\
            access_token_cookie,\
            refresh_token_data,\
            access_token_data = jwt_module.create_login_cookie(
                                            new_user,
                                            flask.request.headers.get('User-Agent'),
                                            flask.request.headers.get('Client-Token', None),
                                            flask.request.remote_addr,
                                            flask.current_app.config.get('SECRET_KEY'))

        response_type: api.Response = AccountResponseCase.user_signed_up
        if mail_sent:
            response_type = AccountResponseCase.user_signed_up_but_mail_error

        return response_type.create_response(
            header=(
                ('Set-Cookie', refresh_token_cookie),
                ('Set-Cookie', access_token_cookie),
            ),
            data={
                'RefreshToken': refresh_token_data,
                'AccessToken': access_token_data,
            }
        )
