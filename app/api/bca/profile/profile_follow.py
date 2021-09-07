import flask
import flask.views

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module

from app.api.response_case import CommonResponseCase, ResourceResponseCase
from app.api.bca.profile.profile_response_case import ProfileResponseCase

db = db_module.db


class ProfileFollowRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def get(self, profile_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Return is requested profile follow this profile
        responses:
            - profile_already_followed
            - profile_not_following
            - multiple_resources_found
            - resource_not_found
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

            profile_1_id, profile_2_id = requested_profile_id, target_profile.uuid
            if profile_1_id > profile_2_id:
                profile_1_id, profile_2_id = profile_2_id, profile_1_id

            profile_follow_rel = db.session.query(profile_module.ProfileFollow)\
                .filter(profile_module.ProfileFollow.profile_1_id == profile_1_id)\
                .filter(profile_module.ProfileFollow.profile_2_id == profile_2_id)\
                .first()
            if not profile_follow_rel:
                return ProfileResponseCase.profile_not_following.create_response()

            if not profile_follow_rel.get_relation_explain()[requested_profile_id, profile_id]:
                return ProfileResponseCase.profile_not_following.create_response()

            # If target profile is marked as private or deleted, then we need to hide this profile's existance
            if target_profile.private or target_profile.deleted_at:
                return ResourceResponseCase.resource_not_found.create_response()

            return ProfileResponseCase.profile_already_followed.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def put(self, profile_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Follow {profile_id} profile. Private cards cannot be followed for now.
        responses:
            - profile_followed
            - multiple_resources_found
            - resource_not_found
            - server_error
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])

            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response()

            target_profile = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .filter(profile_module.Profile.private.is_(False))\
                .filter(profile_module.Profile.uuid == profile_id)\
                .first()
            if not target_profile:
                return ResourceResponseCase.resource_forbidden.create_response()

            # Block self-follow
            if target_profile.user_id == access_token.user:
                return ResourceResponseCase.resource_forbidden.create_response()

            # Query follow relation,
            # and if follow relation is available, check if requested profile is following target profile
            profile_1_id, profile_2_id = requested_profile_id, target_profile.uuid
            if profile_1_id > profile_2_id:
                profile_1_id, profile_2_id = profile_2_id, profile_1_id

            profile_follow_rel = db.session.query(profile_module.ProfileFollow)\
                .filter(profile_module.ProfileFollow.profile_1_id == profile_1_id)\
                .filter(profile_module.ProfileFollow.profile_2_id == profile_2_id)\
                .first()
            if not profile_follow_rel:
                profile_follow_rel = profile_module.ProfileFollow()
                profile_follow_rel.profile_1_id = profile_1_id
                profile_follow_rel.profile_2_id = profile_2_id
                # If it's not working, then we need to query these. Too bad!
                profile_follow_rel.user_1_id = profile_follow_rel.profile_1.user_id
                profile_follow_rel.user_2_id = profile_follow_rel.profile_2.user_id

                profile_follow_rel.mark_as_follow(requested_profile_id)
                db.session.add(profile_follow_rel)
            else:  # OK, there's a follow relation. Check if requested profile is following target profile.
                is_profile_following = profile_follow_rel.get_relation_explain()[(
                    requested_profile_id,
                    target_profile.uuid)]

                if not is_profile_following:
                    # OK, we need to mark user as follow
                    profile_follow_rel.mark_as_follow(requested_profile_id)

            db.session.commit()

            return ProfileResponseCase.profile_followed.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self, profile_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Unfollow {profile_id} profile
        responses:
            - profile_unfollowed
            - multiple_resources_found
            - resource_not_found
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
                return ResourceResponseCase.resource_forbidden.create_response()

            # Block self-unfollow
            if target_profile.user_id == access_token.user:
                return ResourceResponseCase.resource_forbidden.create_response()

            # Query follow relation,
            # and if follow relation is available, check if requested profile is following target profile
            profile_1_id, profile_2_id = requested_profile_id, target_profile.uuid
            if profile_1_id > profile_2_id:
                profile_1_id, profile_2_id = profile_2_id, profile_1_id

            profile_follow_rel = db.session.query(profile_module.ProfileFollow)\
                .filter(profile_module.ProfileFollow.profile_1_id == profile_1_id)\
                .filter(profile_module.ProfileFollow.profile_2_id == profile_2_id)\
                .first()
            if not profile_follow_rel:
                return ProfileResponseCase.profile_not_following.create_response()
            else:
                # OK, there's a follow relation.
                # But, before we get started, we need to unsubscribe all cards.
                db.session.query(profile_module.CardSubscription)\
                    .filter(profile_module.CardSubscription.profile_follow_rel_id == profile_follow_rel.uuid)\
                    .filter(profile_module.CardSubscription.profile_id == requested_profile_id)\
                    .delete()

                # Check if requested profile is following target profile.
                is_profile_following = profile_follow_rel.get_relation_explain()[(
                    requested_profile_id,
                    target_profile.uuid)]

                if not is_profile_following:
                    return ProfileResponseCase.profile_not_following.create_response()

                # OK, we need to mark user as unfollow
                profile_follow_rel.mark_as_unfollow(requested_profile_id)

                # Remove follow relation if both two profiles are not following
                if not profile_follow_rel.when_1_followed_2 and not profile_follow_rel.when_2_followed_1:
                    db.session.delete(profile_follow_rel)

            db.session.commit()

            return ProfileResponseCase.profile_unfollowed.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()
