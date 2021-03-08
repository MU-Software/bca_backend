import datetime
import flask
import flask.views
import jwt

import app.api as api
import app.common.utils as utils
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.user as user_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db


class AccountDeactivationRoute(flask.views.MethodView, api.MethodViewMixin):
    def post(self):
        # Deactivate user itselfs
        delcheck_req = utils.request_body(['email', 'password'])
        if type(delcheck_req) == list:
            return CommonResponseCase.body_required_omitted.create_response(data={'lacks': delcheck_req})
        elif delcheck_req is None:
            return CommonResponseCase.body_invalid.create_response()
        elif not delcheck_req:
            return CommonResponseCase.body_empty.create_response()
        elif type(delcheck_req) != dict:
            return CommonResponseCase.body_invalid.create_response()

        refresh_token_cookie = flask.request.cookies.get('refresh_token', type=str, default='')

        if not refresh_token_cookie:
            return AccountResponseCase.user_not_logged_in.create_response()

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
            return AccountResponseCase.user_not_logged_in.create_response()

        target_user: user_module.User = refresh_token.usertable
        if target_user.email != delcheck_req['email']:
            return AccountResponseCase.user_info_mismatch.create_response(
                        data={'fields': ['email']})
        if not target_user.check_password(delcheck_req['password']):
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
                # how user could get here although user don't have any valid refresh token?
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

        field_column_map = {
            'email': user_module.User.email,
            'id': user_module.User.id,
            'nickname': user_module.User.nickname,
        }
        check_result = list()
        try:
            for field_name, field_value in delcheck_req:
                if user_module.User.query.filter(field_column_map[field_name] == field_value).first():
                    check_result.append(field_name)

            if check_result:
                return AccountResponseCase.user_already_used.create_response(data={
                    'duplicate': check_result
                })
            return AccountResponseCase.user_safe_to_use.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()
