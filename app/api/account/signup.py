import datetime
import flask
import flask.views
import json
from passlib.hash import argon2
import sqlalchemy as sql

import app.api.helper_class as api_class
import app.common.utils as utils
import app.common.mailgun as mailgun
import app.database as db_module
import app.database.user as user
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module
import app.plugin.bca.user_db.file_io as bca_sync_file_io

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db

# SignUp confirmation email will expire after 48 hours
signup_verify_mail_valid_duration: datetime.timedelta = datetime.timedelta(hours=48)


class SignUpRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={
            'User-Agent': {'type': 'string', },
            'X-Csrf-Token': {'type': 'string', },
        },
        optional_fields={'X-Client-Token': {'type': 'string', }, })
    @api_class.RequestBody(
        required_fields={
            'id': {'type': 'string', },
            'pw': {'type': 'string', },
            'nick': {'type': 'string', },
            'email': {'type': 'string', },
        })
    def post(self, req_header, req_body):
        '''
        description: Sign-up with Email
        responses:
            - user_signed_up
            - user_signed_up_but_mail_error
            - user_already_used
            - body_bad_semantics
            - server_error
        '''
        # Normalize all user inputs, including password
        for k, v in req_body.items():
            req_body[k] = utils.normalize(v)

        if not utils.is_email(req_body['email']):
            return CommonResponseCase.body_bad_semantics.create_response(
                data={'bad_semantics': ({'email': 'NOT_A_VALID_EMAIL_ADDRESS'},)})
        if reason := utils.is_useridsafe(req_body['id']):
            return CommonResponseCase.body_bad_semantics.create_response(
                data={'bad_semantics': ({'id': reason},)})
        if reason := utils.is_passwordsafe(req_body['pw']):
            return CommonResponseCase.body_bad_semantics.create_response(
                data={'bad_semantics': ({'pw': reason},)})

        if req_body['pw'] in (req_body['id'], req_body['email'], req_body['nick']):
            reason = 'PW_REUSED_ON_ID_EMAIL_NICK'
            return CommonResponseCase.body_bad_semantics.create_response(
                data={'bad_semantics': ({'pw': reason},)})

        # Create new user
        new_user = user.User()
        new_user.email = req_body['email']
        new_user.id = req_body['id']
        new_user.nickname = req_body['nick']
        new_user.password = argon2.hash(req_body['pw'])
        new_user.pw_changed_at = sql.func.now()
        new_user.last_login_date = sql.func.now()

        # If the TB_USER is empty (=this user is the first registered user),
        # make this user admin and mark email as verified.
        if not db.session.query(user.User).first():
            new_user.role = '["admin"]'
            new_user.email_verified = True

        db.session.add(new_user)

        # Create new profile for this new user
        new_profile = profile_module.Profile()
        new_profile.user = new_user
        new_profile.name = new_user.nickname
        new_profile.description = None

        new_profile.data = json.dumps({
            'email': {
                'index': 0,
                'value': {
                    'default': {'index': 0, 'value': new_user.email, }
                }
            }
        }, ensure_ascii=False)
        new_profile.email = json.dumps({'email': new_user.email, }, ensure_ascii=False)
        db.session.add(new_profile)

        try:
            db.session.commit()
        except Exception as err:
            db.session.rollback()
            err_reason, err_column_name = db_module.IntegrityCaser(err)
            if err_reason == 'FAILED_UNIQUE':
                return AccountResponseCase.user_already_used.create_response(
                    data={'duplicate': [err_column_name, ]})
            else:
                raise err

        # Add profile id on user roles. This must be done after create opetaion to get UUID of profile
        current_role: list = json.loads(new_user.role or '[]')
        current_role.append({'type': 'profile', 'id': new_profile.uuid})
        new_user.role = json.dumps(current_role, ensure_ascii=False)
        db.session.commit()

        mail_sent = True
        MAIL_ENABLE = flask.current_app.config.get('MAIL_ENABLE')
        SIGNIN_POSSIBLE_AFTER_MAIL_VERIFICATION = flask.current_app.config.get(
            'SIGNIN_POSSIBLE_AFTER_MAIL_VERIFICATION')
        if MAIL_ENABLE:
            try:
                # Create email token to verification & confirmation mail
                email_token = user.EmailToken.create(
                    new_user, user.EmailTokenAction.EMAIL_VERIFICATION, signup_verify_mail_valid_duration)

                http_or_https = 'https://' if flask.current_app.config.get('HTTPS_ENABLE', True) else 'http://'
                email_result = flask.render_template(
                    'email/email_verify.html',
                    domain_url=http_or_https + flask.current_app.config.get('SERVER_NAME'),
                    api_base_url=(http_or_https + flask.current_app.config.get('SERVER_NAME')
                                  + '/api/' + flask.current_app.config.get('RESTAPI_VERSION')),
                    project_name=flask.current_app.config.get('PROJECT_NAME'),
                    user_nick=new_user.nickname,
                    email_key=email_token.token,
                    language='kor')

                mail_sent = mailgun.send_mail(
                    fromaddr='do-not-reply@' + flask.current_app.config.get('MAIL_DOMAIN'),
                    toaddr=new_user.email,
                    subject=f'{flask.current_app.config.get("PROJECT_NAME")}??? ?????? ?????? ???????????????!',
                    message=email_result)

                if SIGNIN_POSSIBLE_AFTER_MAIL_VERIFICATION and mail_sent:
                    return AccountResponseCase.user_signed_up_but_need_email_verification.create_response()
            except Exception:
                mail_sent = False

        jwt_data_header, jwt_data_body = jwt_module.create_login_data(
                                            new_user,
                                            req_header.get('User-Agent'),
                                            req_header.get('X-Csrf-Token'),
                                            req_header.get('X-Client-Token', None),
                                            flask.request.remote_addr,
                                            flask.current_app.config.get('SECRET_KEY'))

        response_body = {'user': new_user.to_dict()}
        response_body['user'].update(jwt_data_body)

        # Create and send new user db file
        try:
            user_db_obj = bca_sync_file_io.BCaSyncFile.create(new_user.uuid, True, True)
            file_md5 = user_db_obj.get_hash()
            file_b64 = user_db_obj.as_b64urlsafe()

            jwt_data_header.append(('ETag', file_md5))
            response_body['db': file_b64]
        except Exception:
            pass

        response_type: api_class.Response = AccountResponseCase.user_signed_up
        if not mail_sent:
            response_type = AccountResponseCase.user_signed_up_but_mail_error

        return response_type.create_response(header=jwt_data_header, data=response_body)
