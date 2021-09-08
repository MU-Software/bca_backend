import flask
import flask.views
import sqlalchemy as sql
import typing

import app.api.helper_class as api_class
import app.common.utils as utils
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db


class ProfileFollowerRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={},
        optional_fields={
            'X-Csrf-Token': {'type': 'string', },
            'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: False, })
    def get(self,
            req_header: dict,
            profile_id: typing.Optional[int] = None,
            access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Get follower list of given profile_id.
                     Returns my profile id's follower list if profile_id not given.
        responses:
            - multiple_resources_found
            - resource_not_found
            - resource_forbidden
            - server_error
        '''
        try:
            if not profile_id and (not access_token or req_header.get('X-Profile-Id', None)):
                # if profile_id is not given, then both access_token and X-Profile-Id must be given
                return CommonResponseCase.http_mtd_forbidden.create_response()

            if not profile_id:
                requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
                if str(requested_profile_id) not in access_token.role:
                    return ResourceResponseCase.resource_forbidden.create_response()

                profile_id = requested_profile_id

            target_profile = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .filter(profile_module.Profile.uuid == profile_id)\
                .first()
            if not target_profile:
                return ResourceResponseCase.resource_not_found.create_response(
                    data={'resource_name': ['profile', ]})

            if not target_profile.is_follower_list_public\
               and ('admin' not in access_token.role and target_profile.user_id != access_token.role):
                return ResourceResponseCase.resource_forbidden.create_response()

            if target_profile.private:
                if not access_token:
                    return ResourceResponseCase.resource_forbidden.create_response()

                follow_check = db.session.query(profile_module.ProfileFollow)\
                    .filter(sql.or_(
                        sql.and_(
                            profile_module.ProfileFollow.user_1_id == access_token.user,
                            profile_module.ProfileFollow.profile_2_id == target_profile.uuid,
                            profile_module.ProfileFollow.when_1_followed_2.is_(None), ),
                        sql.and_(
                            profile_module.ProfileFollow.user_2_id == access_token.user,
                            profile_module.ProfileFollow.profile_1_id == target_profile.uuid,
                            profile_module.ProfileFollow.when_2_followed_1.is_(None), ), ), ).first()

                has_power_to_view_following_list: bool = 'admin' in access_token.role\
                    or target_profile.user_id == access_token.user\
                    or follow_check
                if not has_power_to_view_following_list:
                    return ResourceResponseCase.resource_forbidden.create_response()

            profile_follow_rel = db.session.query(profile_module.ProfileFollow)\
                .filter(sql.or_(
                    sql.and_(
                        profile_module.ProfileFollow.profile_1_id == profile_id,
                        profile_module.ProfileFollow.when_2_followed_1.isnot_(None),
                        profile_module.ProfileFollow.profile_2.private.is_(False), ),
                    sql.and_(
                        profile_module.ProfileFollow.profile_2_id == profile_id,
                        profile_module.ProfileFollow.when_1_followed_2.isnot_(None),
                        profile_module.ProfileFollow.profile_1.private.is_(False), ),
                )).all()
            if not profile_follow_rel:
                return ResourceResponseCase.resource_not_found.create_response(
                    data={'resource_name': ['following', ]})

            return ResourceResponseCase.multiple_resources_found.create_response(
                data={
                    'follower': [
                        following.to_dict_reverse_perspective_of(requested_profile_id)
                        for following in profile_follow_rel
                        if following.to_dict_perspective_of(requested_profile_id)[requested_profile_id]
                    ], }, )

        except Exception:
            return CommonResponseCase.server_error.create_response()


class ProfileFollowingRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={},
        optional_fields={
            'X-Csrf-Token': {'type': 'string', },
            'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: False, })
    def get(self,
            req_header: dict,
            profile_id: typing.Optional[int] = None,
            access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Get following profile list of given profile_id.
                     Returns my profile id's following list if profile_id not given.
        responses:
            - multiple_resources_found
            - resource_not_found
            - resource_forbidden
            - server_error
        '''
        try:
            if not profile_id and (not access_token or req_header.get('X-Profile-Id', None)):
                # if profile_id is not given, then both access_token and X-Profile-Id must be given
                return CommonResponseCase.http_mtd_forbidden.create_response()

            if not profile_id:
                requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
                if str(requested_profile_id) not in access_token.role:
                    return ResourceResponseCase.resource_forbidden.create_response()

                profile_id = requested_profile_id

            target_profile = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .filter(profile_module.Profile.uuid == profile_id)\
                .first()
            if not target_profile:
                return ResourceResponseCase.resource_not_found.create_response(
                    data={'resource_name': ['profile', ]})

            if not target_profile.is_following_list_public\
               and ('admin' not in access_token.role and target_profile.user_id != access_token.role):
                return ResourceResponseCase.resource_forbidden.create_response()

            if target_profile.private:
                if not access_token:
                    return ResourceResponseCase.resource_forbidden.create_response()

                follow_check = db.session.query(profile_module.ProfileFollow)\
                    .filter(sql.or_(
                        sql.and_(
                            profile_module.ProfileFollow.user_1_id == access_token.user,
                            profile_module.ProfileFollow.profile_2_id == target_profile.uuid,
                            profile_module.ProfileFollow.when_1_followed_2.is_(None), ),
                        sql.and_(
                            profile_module.ProfileFollow.user_2_id == access_token.user,
                            profile_module.ProfileFollow.profile_1_id == target_profile.uuid,
                            profile_module.ProfileFollow.when_2_followed_1.is_(None), ), ), ).first()

                has_power_to_view_following_list: bool = 'admin' in access_token.role\
                    or target_profile.user_id == access_token.user\
                    or follow_check
                if not has_power_to_view_following_list:
                    return ResourceResponseCase.resource_forbidden.create_response()

            profile_follow_rel = db.session.query(profile_module.ProfileFollow)\
                .filter(sql.or_(
                    sql.and_(
                        profile_module.ProfileFollow.profile_1_id == profile_id,
                        profile_module.ProfileFollow.when_1_followed_2.isnot_(None),
                        profile_module.ProfileFollow.profile_2.private.is_(False), ),
                    sql.and_(
                        profile_module.ProfileFollow.profile_2_id == profile_id,
                        profile_module.ProfileFollow.when_2_followed_1.isnot_(None),
                        profile_module.ProfileFollow.profile_1.private.is_(False), ),
                )).all()
            if not profile_follow_rel:
                return ResourceResponseCase.resource_not_found.create_response(
                    data={'resource_name': ['following', ]})

            return ResourceResponseCase.multiple_resources_found.create_response(
                data={
                    'following': [
                        following.to_dict_perspective_of(requested_profile_id) for following in profile_follow_rel
                        if following.to_dict_perspective_of(requested_profile_id)[requested_profile_id]
                    ], }, )

        except Exception:
            return CommonResponseCase.server_error.create_response()
