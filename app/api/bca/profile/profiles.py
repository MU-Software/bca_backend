import datetime
import flask
import json

import app.api.helper_class as api_class
import app.database as db_module
import app.database.user as user_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module
import app.plugin.bca.sqs_action.action_definition as sqs_action_def

from app.api.response_case import CommonResponseCase, ResourceResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db


class ProfileMainRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={'X-Csrf-Token': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    def get(self, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Get user's all profiles
        responses:
            - multiple_resources_found
            - resource_not_found
            - server_error
        '''
        try:
            target_profiles = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .filter(profile_module.Profile.user_id == access_token.user)\
                .all()
            if not target_profiles:
                return ResourceResponseCase.resource_not_found.create_response(
                            message='You don\'t have any profiles yet')

            return ResourceResponseCase.multiple_resources_found.create_response(
                        data={'profiles': [profile.to_dict() for profile in target_profiles], })

        except Exception:
            CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Csrf-Token': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        required_fields={
            'name': {'type': 'string', },
            'data': {'type': 'string', }, },
        optional_fields={
            'email': {'type': 'string', },
            'phone': {'type': 'string', },
            'sns': {'type': 'string', },
            'description': {'type': 'string', },
            'private': {'type': 'boolean', }, })
    def post(self, req_header: dict, access_token: jwt_module.AccessToken, req_body: dict):
        '''
        description: Create new profile
        responses:
            - user_not_found
            - resource_created
            - server_error
        '''
        try:
            # Get user data from table using access token
            target_user = db.session.query(user_module.User)\
                .filter(user_module.User.deactivated_at.is_(None))\
                .filter(user_module.User.locked_at.is_(None))\
                .filter(user_module.User.uuid == access_token.user)\
                .first()
            if not target_user:
                return AccountResponseCase.user_not_found.create_response()

            new_profile = profile_module.Profile()
            new_profile.user_id = target_user.uuid
            new_profile.name = req_body['name']
            new_profile.data = req_body['data']
            new_profile.email = req_body.get('email', None)
            new_profile.phone = req_body.get('phone', None)
            new_profile.sns = req_body.get('sns', None)
            new_profile.description = req_body.get('description', None)
            new_profile.private = bool(req_body.get('private', False))

            db.session.add(new_profile)
            db.session.commit()

            # Add profile id on user roles
            current_role: list = json.loads(target_user.role)
            current_role.append({'type': 'profile', 'id': new_profile.uuid})
            target_user.role = json.dumps(current_role)
            db.session.commit()

            # Revoke access token so that user renews their access token that includes all of his/her profile ids
            query_result = db.session.query(jwt_module.RefreshToken)\
                .filter(jwt_module.RefreshToken.user == target_user.uuid).all()
            if not query_result:
                # How could this happend?
                return AccountResponseCase.access_token_invalid.create_response(
                    message='User or JWT that mapped to that user not found')

            for target in query_result:
                # TODO: set can set multiple at once, so use that method instead
                redis_key = db_module.RedisKeyType.TOKEN_REVOKE.as_redis_key(target.jti)
                redis_db.set(redis_key, 'revoked', datetime.timedelta(weeks=2))

            # Apply new card data to user db
            # This must be done after commit to get commit_id and modified_at columns' data
            sqs_action_def.profile_created(new_profile)

            return ResourceResponseCase.resource_created.create_response(
                header=(('ETag', new_profile.commit_id, ), ),
                data={'profile': new_profile.to_dict(), })
        except Exception:
            return CommonResponseCase.server_error.create_response()
