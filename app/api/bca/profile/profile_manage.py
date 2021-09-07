import datetime
import flask
import flask.views
import sqlalchemy as sql
import typing

import app.api.helper_class as api_class
import app.common.utils as utils
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module
import app.plugin.bca.sqs_action.action_definition as sqs_action_def

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db


class ProfileManagementRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={},
        optional_fields={'X-Csrf-Token': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: False, })
    def get(self, profile_id: int, req_header: dict, access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Get profile data of given profile_id
        responses:
            - resource_found
            - resource_not_found
            - resource_forbidden
            - server_error
        '''
        try:
            target_profile = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.uuid == profile_id)\
                .first()
            if not target_profile:
                return ResourceResponseCase.resource_not_found.create_response()

            if target_profile.private or target_profile.deleted_at is not None:
                # Check if profile is user's or user already subscribed this profile's card,
                # this will check only if access token is given, if not, then this will be failed.
                if not access_token:
                    return ResourceResponseCase.resource_forbidden.create_response()

                elif 'admin' in access_token.role:
                    return ResourceResponseCase.resource_found.create_response(
                        header=(('ETag', target_profile.commit_id, ), ),
                        data={'profile': target_profile.to_dict(), })

                # Check if profile already subscribed the card
                profile_follow_rel = db.session.query(profile_module.ProfileFollow)\
                    .filter(sql.or_(
                        profile_module.ProfileFollow.profile_1_id == target_profile.uuid,
                        profile_module.ProfileFollow.profile_2_id == target_profile.uuid, ))\
                    .filter(sql.or_(
                        profile_module.ProfileFollow.user_1_id == access_token.user,
                        profile_module.ProfileFollow.user_2_id == access_token.user, ))\
                    .first()

                if target_profile.private and (target_profile.user_id == access_token.user or profile_follow_rel):
                    return ResourceResponseCase.resource_found.create_response(
                        header=(('ETag', target_profile.commit_id, ), ),
                        data={'profile': target_profile.to_dict(), })

                elif target_profile.deleted_at and profile_follow_rel:
                    return ResourceResponseCase.resource_found.create_response(
                        header=(('ETag', target_profile.commit_id, ), ),
                        data={'profile': target_profile.to_dict(), })

                return ResourceResponseCase.resource_forbidden.create_response()

            return ResourceResponseCase.resource_found.create_response(
                header=(('ETag', target_profile.commit_id, ), ),
                data={'profile': target_profile.to_dict(), })
        except Exception:
            return CommonResponseCase.server_error.create_response()

    # # Modify profile
    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'If-Match': {'type': 'string', },
        },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        required_fields={},
        optional_fields={
            'email': {'type': 'string', },
            'phone': {'type': 'string', },
            'sns': {'type': 'string', },
            'description': {'type': 'string', },
            'data': {'type': 'string', },
            'private': {'type': 'boolean', }, })
    def patch(self, profile_id: int, req_header: dict, req_body: dict, access_token: jwt_module.AccessToken):
        '''
        description: Modify user's {profile_id} profile
        responses:
            - resource_modified
            - resource_not_found
            - resource_forbidden
            - resource_prediction_failed
            - server_error
        '''
        try:
            target_profile = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .filter(profile_module.Profile.uuid == profile_id)\
                .first()
            if not target_profile:
                return ResourceResponseCase.resource_not_found.create_response()
            if target_profile.user_id != access_token.user:
                # Check requested user is the owner of the profile
                return ResourceResponseCase.resource_forbidden.create_response()

            # Check Etag
            if target_profile.commit_id != req_header.get('If-Match', None):
                return ResourceResponseCase.resource_prediction_failed.create_response()

            # Modify this profile
            editable_columns = ('email', 'phone', 'sns', 'description', 'data', 'private')
            filtered_data = {col: data for col, data in editable_columns if col in req_body.items()}
            if not filtered_data:
                return CommonResponseCase.body_empty.create_response()
            for column, data in filtered_data.items():
                setattr(target_profile, column, data)

            # Calculate changeset of row, commit, and get commit_id
            changeset: dict[str, list] = utils.get_model_changes(target_profile)
            db_module.db.session.commit()
            changeset['commit_id'] = [None, target_profile.commit_id]
            changeset['modified_at'] = [None, target_profile.modified_at]

            # Now, create and apply this on user db
            sqs_action_def.profile_modified(target_profile, changeset)

            return ResourceResponseCase.resource_deleted.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'If-Match': {'type': 'string', },
        },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self, profile_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Delete user's {profile_id} profile
        responses:
            - resource_deleted
            - resource_not_found
            - resource_forbidden
            - resource_prediction_failed
            - server_error
        '''
        try:
            target_profile = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .filter(profile_module.Profile.uuid == profile_id)\
                .first()
            if not target_profile:
                return ResourceResponseCase.resource_not_found.create_response()
            if target_profile.user_id != access_token.user and 'admin' not in access_token.role:
                # Check requested user is admin or the owner of the profile
                return ResourceResponseCase.resource_forbidden.create_response()

            # Check Etag
            if target_profile.commit_id != req_header.get('If-Match', None):
                return ResourceResponseCase.resource_prediction_failed.create_response()

            deleted_at_time = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)

            # Mark this profile as deleted
            target_profile.deleted_at = deleted_at_time
            target_profile.deleted_by_id = access_token.user
            target_profile.why_deleted = 'DELETE_REQUESTED'

            # Mark cards of this profile as deleted
            db.session.query(profile_module.Card)\
                .filter(profile_module.Card.profile_id == target_profile.uuid)\
                .update({
                    'deleted_at': deleted_at_time,
                    'why_deleted': 'PROFILE_DELETE_REQUESTED',
                    'deleted_by_id': access_token.user, })

            # Calculate changeset of row, commit, and get commit_id
            changeset: dict[str, list] = utils.get_model_changes(target_profile)
            db_module.db.session.commit()
            changeset['commit_id'] = [None, target_profile.commit_id]
            changeset['modified_at'] = [None, target_profile.modified_at]

            # Now, create and apply this on user db
            sqs_action_def.profile_modified(target_profile, changeset)

            return ResourceResponseCase.resource_deleted.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()
