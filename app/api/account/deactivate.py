import datetime
import flask
import flask.views
import jwt

import app.api.helper_class as api_class
import app.common.utils as utils
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.user as user_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db


class AccountDeactivationRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestBody(
        required_fields={
            'email': {'type': 'string', },
            'password': {'type': 'string', },
        })
    def post(self, req_body):
        '''
        description: Sign-in by email or id
        responses:
            - user_not_signed_in
            - user_info_mismatch
            - user_locked
            - user_deactivated
            - user_wrong_password
            - refresh_token_expired
            - refresh_token_invalid
            - server_error
        '''
        # Self-deactivate account route

        refresh_token_cookie = flask.request.cookies.get('refresh_token', type=str, default='')

        if not refresh_token_cookie:
            return AccountResponseCase.user_not_signed_in.create_response()

        try:
            refresh_token: jwt_module.RefreshToken = jwt_module.RefreshToken.from_token(
                                                        refresh_token_cookie,
                                                        flask.current_app.config.get('SECRET_KEY'))

        except jwt.exceptions.ExpiredSignatureError:
            return AccountResponseCase.refresh_token_expired.create_response()
        except jwt.exceptions.InvalidTokenError:
            return AccountResponseCase.refresh_token_invalid.create_response()
        except Exception:
            # Unexpected thing happened while decoding login data. please re-login
            return AccountResponseCase.refresh_token_invalid.create_response()
        if not refresh_token:
            return AccountResponseCase.user_not_signed_in.create_response()

        target_user: user_module.User = refresh_token.usertable
        if target_user.email != req_body['email']:
            return AccountResponseCase.user_info_mismatch.create_response(
                        data={'fields': ['email']})
        if not target_user.check_password(req_body['password']):
            return AccountResponseCase.user_wrong_password.create_response()

        if target_user.locked_at:
            why_locked: str = target_user.why_locked.replace('ACCOUNT_LOCKED::', '')
            return AccountResponseCase.user_locked.create_response(data={'reason': why_locked})
        elif target_user.deactivated_at:
            why_deactivated: str = target_user.why_deactivated.replace('ACCOUNT_DEACTIVATED::', '')
            return AccountResponseCase.user_deactivated.create_response(data={'reason': why_deactivated})

        try:
            # Revoke all user tokens
            target_tokens = jwt_module.RefreshToken.query\
                                .filter(jwt_module.RefreshToken.user == target_user.uuid)\
                                .all()
            if not target_tokens:
                # No refresh token of target user don't make any sense,
                # how could user get here although user don't have any valid refresh token?
                return CommonResponseCase.server_error.create_response()
            for token in target_tokens:
                db.session.delete(token)

                # TODO: set can set multiple at once, so use that method instead
                redis_db.set('refresh_revoke=' + str(token.jti), 'revoked', datetime.timedelta(weeks=2))

            target_user.deactivated_at = datetime.datetime.utcnow().replace(tz=utils.UTC)
            target_user.why_deactivated = 'ACCOUNT_LOCKED::USER_SELF_LOCKED'
            target_user.deactivated_by_orm = target_user
            db.session.commit()
        except Exception:
            return CommonResponseCase.server_error.create_response()

        return AccountResponseCase.user_deactivate_success.create_response()
