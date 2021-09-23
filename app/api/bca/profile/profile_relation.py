import flask
import flask.views

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module

from app.api.response_case import CommonResponseCase, ResourceResponseCase
from app.api.bca.profile.profilerelation_response_case import ProfileRelationResponseCase

db = db_module.db


class ProfileRelationRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def get(self, profile_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Returns requested profile has relationship with profile_id profile
        responses:
            - profilerelation_follows
            - profilerelation_blocks
            - profilerelation_hides
            - profilerelation_not_related
            - resource_not_found
            - resource_forbidden
            - server_error
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])

            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response()

            target_profile = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.uuid == profile_id)\
                .first()
            if not target_profile:
                return ResourceResponseCase.resource_not_found.create_response(
                    data={'resource_name': ['profile', ]})

            profile_follow_rel = db.session.query(profile_module.ProfileRelation)\
                .filter(profile_module.ProfileRelation.from_profile_id == requested_profile_id)\
                .filter(profile_module.ProfileRelation.to_profile_id == target_profile.uuid)\
                .first()
            if not profile_follow_rel:
                # If target profile is marked as private or deleted, then we need to hide this profile's existance
                if target_profile.private or target_profile.deleted_at:
                    return ResourceResponseCase.resource_not_found.create_response()

                return ProfileRelationResponseCase.profilerelation_not_related.create_response()

            if profile_follow_rel.status == profile_module.ProfileRelationStatus.FOLLOW:
                return ProfileRelationResponseCase.profilerelation_follows.create_response()
            elif profile_follow_rel.status == profile_module.ProfileRelationStatus.FOLLOW_REQUESTED:
                return ProfileRelationResponseCase.profilerelation_follow_requests.create_response()
            elif profile_follow_rel.status == profile_module.ProfileRelationStatus.BLOCK:
                return ProfileRelationResponseCase.profilerelation_blocks.create_response()
            elif profile_follow_rel.status == profile_module.ProfileRelationStatus.HIDE:
                return ProfileRelationResponseCase.profilerelation_hides.create_response()
            else:
                return ProfileRelationResponseCase.profilerelation_not_related.create_response()

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(optional_fields={'status': {'type': 'string', }, }, )
    def put(self, profile_id: int, req_header: dict, access_token: jwt_module.AccessToken, req_body: dict):
        '''
        description: Set relationship status to {profile_id} profile.
            User can't create relationship with private profile for now.
        responses:
            - profilerelation_follows
            - profilerelation_blocks
            - profilerelation_hides
            - profilerelation_already_in_state
            - profilerelation_not_related
            - resource_not_found
            - resource_forbidden
            - server_error
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response()

            # Parse status
            target_status: profile_module.ProfileRelationStatus = None
            try:
                target_status = profile_module.ProfileRelationStatus[req_body.get('status', 'FOLLOW').upper()]
            except Exception:
                return CommonResponseCase.body_bad_semantics.create_response(
                    data={'bad_semantics': [{
                        'field': 'status',
                        'reason': 'status must be one of (FOLLOW | FOLLOW_REQUESTED | BLOCK | HIDE)'
                    }, ]})

            target_profile = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .filter(profile_module.Profile.uuid == profile_id)\
                .first()
            if not target_profile:
                return ResourceResponseCase.resource_not_found.create_response()

            # Block self-relationship
            if target_profile.user_id == access_token.user:
                return ResourceResponseCase.resource_forbidden.create_response()

            # Query relationship with those two profiles.
            # Modify state if it's exist, and if it's not, then create.
            profile_relationship = db.session.query(profile_module.ProfileRelation)\
                .filter(profile_module.ProfileRelation.from_profile_id == requested_profile_id)\
                .filter(profile_module.ProfileRelation.to_profile_id == target_profile.uuid)\
                .first()
            if not profile_relationship:
                if target_status == profile_module.ProfileRelationStatus.HIDE:
                    return ProfileRelationResponseCase.profilerelation_not_related.create_response()

                profile_relationship = profile_module.ProfileRelation()
                profile_relationship.from_user_id = access_token.user
                profile_relationship.from_profile_id = requested_profile_id
                profile_relationship.to_user_id = target_profile.user_id
                profile_relationship.to_profile_id = target_profile.uuid

                if target_profile.private and target_status == profile_module.ProfileRelationStatus.FOLLOW:
                    profile_relationship.status = profile_module.ProfileRelationStatus.FOLLOW_REQUESTED

                db.session.add(profile_relationship)
            else:
                if profile_relationship.status == target_status:
                    return ProfileRelationResponseCase.profilerelation_already_in_state.create_response()
                elif profile_relationship.status == profile_module.ProfileRelationStatus.FOLLOW_REQUESTED\
                    and target_status in (
                        profile_module.ProfileRelationStatus.FOLLOW,
                        profile_module.ProfileRelationStatus.HIDE):
                    return ProfileRelationResponseCase.profilerelation_in_follow_request_state.create_response()

                profile_relationship.status = target_status
            db.session.commit()

            if target_status == profile_module.ProfileRelationStatus.FOLLOW:
                return ProfileRelationResponseCase.profilerelation_follows.create_response()
            elif target_status == profile_module.ProfileRelationStatus.FOLLOW_REQUESTED:
                return ProfileRelationResponseCase.profilerelation_follow_requests.create_response()
            elif target_status == profile_module.ProfileRelationStatus.BLOCK:
                return ProfileRelationResponseCase.profilerelation_blocks.create_response()
            elif target_status == profile_module.ProfileRelationStatus.HIDE:
                return ProfileRelationResponseCase.profilerelation_hides.create_response()
            else:
                return ProfileRelationResponseCase.profilerelation_follows.create_response()

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self, profile_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Cut off relationship with {profile_id} profile
        responses:
            - profilerelation_cut_off
            - profilerelation_not_related
            - resource_not_found
            - resource_forbidden
            - server_error
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response()

            target_profile = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.uuid == profile_id)\
                .first()
            if not target_profile:
                return ResourceResponseCase.resource_not_found.create_response()

            # Block self-unfollow
            if target_profile.user_id == access_token.user:
                return ResourceResponseCase.resource_forbidden.create_response()

            # Query relationship with those two profiles, and delete it.
            profile_relationship = db.session.query(profile_module.ProfileRelation)\
                .filter(profile_module.ProfileRelation.from_profile_id == requested_profile_id)\
                .filter(profile_module.ProfileRelation.to_profile_id == target_profile.uuid)\
                .first()
            if not profile_relationship:
                return ProfileRelationResponseCase.profilerelation_not_related.create_response()

            db.session.delete(profile_relationship)
            db.session.commit()

            return ProfileRelationResponseCase.profilerelation_cut_off.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()
