import datetime
import flask

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.user as user_module
import app.database.jwt as jwt_module
import app.database.profile as profile_module
import app.bca.sqs_action.action_definition as sqs_action_def

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase
from app.api.profiles.profile_response_case import ProfileResponseCase

redis_db = db_module.redis_db


class ProfileMainRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={'X-Csrf-Token': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    def get(self, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Get user's all profiles
        responses:
            - multiple_profiles_found
            - profile_not_found
            - server_error
        '''
        try:
            target_profiles: list[profile_module.Profile] = profile_module.Profile.query\
                .filter(profile_module.Profile.user_id == access_token.user)\
                .filter(profile_module.Profile.locked_at == None)\
                .filter(profile_module.Profile.deleted_at == None)\
                .all()  # noqa
            if not target_profiles:
                return ProfileResponseCase.profile_not_found.create_response(
                            message='You don\'t have any profiles yet')

            return ProfileResponseCase.multiple_profiles_found.create_response(
                        data={'profiles': [profile.to_dict() for profile in target_profiles], })

        except Exception:
            # TODO: Check DB error
            CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Csrf-Token': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        required_fields={'name': {'type': 'string', }, },
        optional_fields={
            'email': {'type': 'string', },
            'phone': {'type': 'string', },
            'sns': {'type': 'string', },
            'description': {'type': 'string', },
            'data': {'type': 'string', },
            'private': {'type': 'boolean', }, })
    def post(self,
             req_header: dict,
             access_token: jwt_module.AccessToken,
             req_body: dict):
        '''
        description: Create new profile
        responses:
            - user_not_found
            - profile_created
            - server_error
        '''
        try:
            # Get user data from table using access token
            target_user: user_module.User = user_module.User.query\
                .filter(user_module.User.uuid == access_token.user)\
                .filter(user_module.User.deactivated_at == None)\
                .filter(user_module.User.locked_at == None)\
                .first()  # noqa
            if not target_user:
                return AccountResponseCase.user_not_found.create_response()

            new_profile = profile_module.Profile()
            new_profile.user_id = access_token.user
            new_profile.name = req_body['name']
            new_profile.email = req_body.get('email', None)
            new_profile.phone = req_body.get('phone', None)
            new_profile.sns = req_body.get('sns', None)
            new_profile.description = req_body.get('description', None)
            new_profile.data = req_body.get('data', None)
            new_profile.private = bool(req_body.get('private', False))

            db_module.db.session.add(new_profile)
            db_module.db.session.commit()

            # Revoke access token so that user renews their access token that includes all of his/her profile ids
            query_result = jwt_module.RefreshToken.query\
                .filter(jwt_module.RefreshToken.user == access_token.user).all()
            if not query_result:
                return AccountResponseCase.access_token_invalid.create_response(
                    message='User or JWT that mapped to that user not found')

            for target in query_result:
                # TODO: set can set multiple at once, so use that method instead
                redis_db.set('refresh_revoke=' + str(target.jti), 'revoked', datetime.timedelta(weeks=2))

            # Apply new card data to user db
            try:
                sqs_action_def.card_created(new_profile)
            except Exception as err:
                print(utils.get_traceback_msg(err))

            return ProfileResponseCase.profile_created.create_response(
                header=(('ETag', new_profile.commit_id), ),
                data={'profile': new_profile.to_dict(), })
        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()
