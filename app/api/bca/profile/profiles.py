import datetime
import flask
import json
import typing

import app.api.helper_class as api_class
import app.database as db_module
import app.database.user as user_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module
import app.plugin.bca.user_db.journal_handler as user_db_journal

from app.api.response_case import CommonResponseCase, ResourceResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db


class ProfileMainRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(auth={api_class.AuthType.Bearer: True, })
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
                            message='만드신 프로필이 없습니다.')

            return ResourceResponseCase.multiple_resources_found.create_response(
                        data={'profiles': [profile.to_dict() for profile in target_profiles], })

        except Exception:
            CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        required_fields={
            'name': {'type': 'string', },
            'data': {'type': 'string', }, },
        optional_fields={
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
            new_profile.data = json.dumps(req_body['data'], ensure_ascii=False)
            new_profile.description = req_body.get('description', None)
            new_profile.private = bool(req_body.get('private', True))

            # We must handle 'data' field specially. Parse data and modify proper columns
            # We need to get first item in columns
            profile_data: dict[str, dict[str, typing.Any]] = req_body['data']
            if isinstance(profile_data, str):
                profile_data = json.loads(profile_data)
            filtered_profile_data: dict[str, str] = dict()

            listize_target_fields = ['email', 'phone', 'sns', 'address']
            for field in listize_target_fields:
                field_data: dict[str, dict[str, typing.Any]] = profile_data.get(field, {'value': None})['value']
                if not field_data:
                    continue

                field_data: list[tuple[str, int, str]] = [(k, v['index'], v['value']) for k, v in field_data.items()]
                field_data.sort(key=lambda i: i[1])
                field_data = field_data[0]

                filtered_profile_data[field] = json.dumps({field_data[0]: field_data[2], }, ensure_ascii=False)

            # And set proper values on orm object
            editable_columns = ('email', 'phone', 'sns', 'address')
            filtered_data = {col: data for col, data in filtered_profile_data.items() if col in editable_columns}
            for column, data in filtered_data.items():
                setattr(new_profile, column, json.dumps(data, ensure_ascii=False))

            # Add to db
            db.session.add(new_profile)

            # Apply changeset on both user db and service db
            with user_db_journal.UserDBJournalCreator(db):
                db.session.commit()

            # Add profile id on user roles. This must be done after create opetaion to get UUID of profile
            current_role: list = json.loads(target_user.role)
            current_role.append({'type': 'profile', 'id': new_profile.uuid})
            target_user.role = json.dumps(current_role, ensure_ascii=False)
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

            return ResourceResponseCase.resource_created.create_response(
                header=(('ETag', new_profile.commit_id, ), ),
                data={'profile': new_profile.to_dict(), })
        except Exception:
            return CommonResponseCase.server_error.create_response()
