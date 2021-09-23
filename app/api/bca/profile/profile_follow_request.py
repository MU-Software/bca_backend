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


class ProfileFollowRequestRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer'}, },
        auth={api_class.AuthType.Bearer: True, })
    def get(self, profile_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Returns all follow-requests.
        responses:
            - multiple_resources_found
            - resource_not_found
            - server_error
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

            target_follow_request_rels = db.session.query(profile_module.ProfileRelation)\
                .filter(profile_module.ProfileRelation.to_profile_id == requested_profile_id)\
                .filter(profile_module.ProfileRelation.status == profile_module.ProfileRelationStatus.FOLLOW_REQUESTED)\
                .all()
            if not target_follow_request_rels:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='팔로우 요청이 없습니다.')

            return ResourceResponseCase.multiple_resources_found.create_response(
                data={'follow_requests': [pr.from_profile.to_dict() for pr in target_follow_request_rels], })

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer'}, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(required_fields={'target_profile': {'type': 'integer'}}, )
    def put(self, profile_id: int, req_header: dict, access_token: jwt_module.AccessToken, req_body: dict):
        '''
        description: Allow follow-request as follow.
        responses:
            - multiple_resources_found
            - resource_not_found
            - server_error
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

            target_follow_request_rel = db.session.query(profile_module.ProfileRelation)\
                .filter(profile_module.ProfileRelation.from_profile_id == req_body['target_profile'])\
                .filter(profile_module.ProfileRelation.to_profile_id == requested_profile_id)\
                .filter(profile_module.ProfileRelation.status == profile_module.ProfileRelationStatus.FOLLOW_REQUESTED)\
                .first()
            if not target_follow_request_rel:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='팔로우 요청이 없습니다.')

            target_follow_request_rel.status = profile_module.ProfileRelationStatus.FOLLOW
            db.session.commit()

            return ProfileRelationResponseCase.profilerelation_follows.create_response(code=201)

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer'}, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(required_fields={'target_profile': {'type': 'integer'}}, )
    def delete(self, profile_id: int, req_header: dict, access_token: jwt_module.AccessToken, req_body: dict):
        '''
        description: Deny follow-request.
        responses:
            - multiple_resources_found
            - resource_not_found
            - server_error
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

            target_follow_request_rel = db.session.query(profile_module.ProfileRelation)\
                .filter(profile_module.ProfileRelation.from_profile_id == req_body['target_profile'])\
                .filter(profile_module.ProfileRelation.to_profile_id == requested_profile_id)\
                .filter(profile_module.ProfileRelation.status == profile_module.ProfileRelationStatus.FOLLOW_REQUESTED)\
                .first()
            if not target_follow_request_rel:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='팔로우 요청이 없습니다.')

            db.session.delete(target_follow_request_rel)
            db.session.commit()

            return ProfileRelationResponseCase.profilerelation_cut_off.create_response()

        except Exception:
            return CommonResponseCase.server_error.create_response()
