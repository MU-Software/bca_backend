import flask
import flask.views
import json

import app.api.helper_class as api_class
import app.api.common.file_manage as route_filemgr
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module
import app.plugin.bca.user_db.sqs_action as sqs_action

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db


# We had to handle profile image on separate route,
# as we wanted to add ability to delete profile image.
class ProfileImageManagementRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={'If-Match': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    def patch(self, profile_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Modify {profile_id} profile's image. This can be done only by the owner.
        responses:
            - resource_modified
            - resource_not_found
            - resource_forbidden
            - resource_prediction_failed
            - server_error
        '''
        target_profile = db.session.query(profile_module.Profile)\
            .filter(profile_module.Profile.locked_at.is_(None))\
            .filter(profile_module.Profile.deleted_at.is_(None))\
            .filter(profile_module.Profile.uuid == profile_id)\
            .first()
        if not target_profile:
            return ResourceResponseCase.resource_not_found.create_response(
                message='프로필을 찾을 수 없습니다.')
        if target_profile.user_id != access_token.user:
            # Check requested user is the owner of the profile
            return ResourceResponseCase.resource_forbidden.create_response(
                message='프로필을 제작한 사람만이 프로필을 수정할 수 있습니다..')

        # Check Etag
        if target_profile.commit_id != req_header.get('If-Match', None):
            return ResourceResponseCase.resource_prediction_failed.create_response(
                message='프로필이 다른 기기에서 수정된 것 같습니다.\n동기화를 해 주세요.')

        # We'll handle upload first to make sure whether upload process success.
        # We can't revert this when error raised if we delete files first.
        # This calls internal REST API
        up_result: api_class.ResponseType = route_filemgr.FileManagementRoute().post()
        up_res_body, up_res_code, up_res_header = up_result
        if up_res_code != 201:  # Upload failed
            return up_result
        up_res_body = json.loads(up_res_body.data)

        if target_profile.image_url:
            target_file: str = target_profile.image_url.replace('/uploads/', '').replace('/', '').strip()
            # This calls internal REST API
            del_result: api_class.ResponseType = route_filemgr.FileManagementRoute().delete(filename=target_file)
            del_res_body, del_res_code, del_res_header = del_result
            if del_res_code != 204:  # Deletion didn't done completely.
                return CommonResponseCase.server_error.create_response()

        target_profile.image_url = up_res_body['data']['file']['url']

        # Apply changeset on user db
        with sqs_action.UserDBJournalCreator(db):
            db.session.commit()

        return ResourceResponseCase.resource_modified.create_response()

    @api_class.RequestHeader(
        required_fields={'If-Match': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self, profile_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Delete user's {profile_id} profile image. This can be done by admin or the owner.
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
                return ResourceResponseCase.resource_not_found.create_response(
                    message='프로필을 찾을 수 없습니다.')
            if target_profile.user_id != access_token.user and 'admin' not in access_token.role:
                # Check requested user is admin or the owner of the profile
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='프로필 사진은 관리자나 해당 명함의 주인만이 삭제할 수 있습니다.')

            # Check Etag
            if target_profile.commit_id != req_header.get('If-Match', None):
                return ResourceResponseCase.resource_prediction_failed.create_response(
                    message='프로필이 다른 기기에서 수정된 것 같습니다.\n동기화를 해 주세요.')

            target_file: str = target_profile.image_url.replace('/uploads/', '').replace('/', '').strip()
            # Internal REST API call
            del_result: api_class.ResponseType = route_filemgr.FileManagementRoute().delete(filename=target_file)
            del_res_body, del_res_code, del_res_header = del_result
            if del_res_code != 204:
                # Deletion didn't done completely.
                return CommonResponseCase.server_error.create_response()

            target_profile.image_url = None
            db.session.commit()
            return ResourceResponseCase.resource_modified.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()
