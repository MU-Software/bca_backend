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
    @api_class.RequestBody(
        required_fields={'name': {'type': 'string', }, },
        optional_fields={
            'email': {'type': 'string', },
            'phone': {'type': 'string', },
            'sns': {'type': 'string', },
            'description': {'type': 'string', },
            'additional_data': {'type': 'string', },
            'private': {'type': 'boolean', },
        })
    def post(self,
             req_header: dict,
             access_token: jwt_module.AccessToken,
             req_body: dict):
        '''
        description: Create new profile
        responses:
            - access_token_invalid
            - profile_created
            - server_error
        '''
        try:
            # Get user data from table using access token
            target_user: user_module.User = user_module.User.query\
                .filter(user_module.User.uuid == access_token.user)\
                .filter(user_module.User.deactivated_at is not None)\
                .filter(user_module.User.locked_at is not None)\
                .first()
            if not target_user:
                return AccountResponseCase.access_token_invalid.create_response()

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
                data=new_profile.to_dict(),
                header=(
                    ('ETag', new_profile.commit_id),
                    ('Last-Modified', new_profile.modified_at),
                ))
        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()
