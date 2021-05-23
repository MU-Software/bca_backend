import flask

import app.api.helper_class as api_class
import app.database as db_module
import app.database.user as user_module
import app.database.jwt as jwt_module
import app.database.profile as profile_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase
from app.api.profiles.profile_response_case import ProfileResponseCase


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
            new_profile.private = bool(req_body.get('private', False))

            db_module.db.session.add(new_profile)
            db_module.db.session.commit()

            return ProfileResponseCase.profile_created.create_response(
                header=(('ETag', new_profile.commit_id), ),
                data={'profile': new_profile.to_dict(), })
        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()
