import datetime
import flask
import flask.views
import sqlalchemy as sql
import json
import typing

import app.api.helper_class as api_class
import app.common.utils as utils
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module
import app.database.bca.chat as chat_module
import app.plugin.bca.sqs_action as sqs_action

from app.api.response_case import CommonResponseCase, ResourceResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db


class ProfileManagementRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        optional_fields={'X-Profile-Id': {'type': 'integer'}, },
        auth={api_class.AuthType.Bearer: False, })
    def get(self, profile_id: int, req_header: dict, access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Get profile data of given profile_id. Private profiles can be view only by the followers and admin.
        responses:
            - resource_found
            - resource_not_found
            - resource_forbidden
            - server_error
        '''
        try:
            # Need to check is requested profile is following target profile,
            # First, we need to check if X-Profile-Id is valid
            requested_profile_id = utils.safe_int(req_header.get('X-Profile-Id', 0))
            if 'X-Profile-Id' in req_header and str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

            target_profile = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.uuid == profile_id)\
                .first()
            if not target_profile:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='해당 프로필을 찾을 수 없습니다.')

            if target_profile.private or target_profile.deleted_at:
                # Check if profile is requested user's or user already subscribed this profile's card.
                # this will check only if access token is given, if not, then this will be failed.
                if not access_token:
                    return ResourceResponseCase.resource_forbidden.create_response(
                        message='해당 프로필을 볼 권한이 없습니다.')

                elif 'admin' in access_token.role:
                    return ResourceResponseCase.resource_found.create_response(
                        header=(('ETag', target_profile.commit_id, ), ),
                        data={'profile': target_profile.to_dict(), })

                elif target_profile.user_id == access_token.user and not target_profile.deleted_at:
                    return ResourceResponseCase.resource_found.create_response(
                        header=(('ETag', target_profile.commit_id, ), ),
                        data={'profile': target_profile.to_dict(), })

                # Second, Check if there's a follow relationship between requested profile and target profile
                profile_rels = db.session.query(profile_module.ProfileRelation)\
                    .filter(
                        sql.or_(
                            sql.and_(
                                profile_module.ProfileRelation.from_profile_id == requested_profile_id,
                                profile_module.ProfileRelation.to_profile_id == target_profile.uuid, ),
                            sql.and_(
                                profile_module.ProfileRelation.from_profile_id == target_profile.uuid,
                                profile_module.ProfileRelation.to_profile_id == requested_profile_id, ), ),
                    ).all()
                profile_i_follow_opponent_rel = [
                    pr for pr in profile_rels if pr.status in (
                        profile_module.ProfileRelationStatus.FOLLOW,
                        profile_module.ProfileRelationStatus.HIDE, )
                    and pr.from_profile_id == requested_profile_id and pr.to_profile_id == target_profile.uuid]
                profile_opponent_follows_me_rel = [
                    pr for pr in profile_rels if pr.status in (
                        profile_module.ProfileRelationStatus.FOLLOW,
                        profile_module.ProfileRelationStatus.HIDE, )
                    and pr.from_profile_id == target_profile.uuid and pr.to_profile_id == requested_profile_id]
                profile_opponent_blocks_me_rel = [
                    pr for pr in profile_rels
                    if pr.status == profile_module.ProfileRelationStatus.BLOCK
                    and pr.from_profile_id == target_profile.uuid and pr.to_profile_id == requested_profile_id]
                # profile_i_blocked_opponent_rel = [
                #     pr for pr in profile_rels
                #     if pr.status == profile_module.ProfileRelationStatus.BLOCK
                #     and pr.from_profile_id == requested_profile_id and pr.to_profile_id == target_profile.uuid]
                profile_opponent_requests_follow_to_me_rel = [
                    pr for pr in profile_rels
                    if pr.status == profile_module.ProfileRelationStatus.FOLLOW_REQUESTED
                    and pr.from_profile_id == requested_profile_id and pr.to_profile_id == target_profile.uuid]

                # If profile is deleted, then I can see the profile only if I already follow that profile.
                # And if profile is private, then
                #   - I follow opponent or opponent follows me,
                #   - Opponent blocked me, but there's any relation (except block) between me and opponent,
                #   - Opponent requested follow to me,
                # then we can see opponent's profile.
                if target_profile.deleted_at and profile_i_follow_opponent_rel:
                    return ResourceResponseCase.resource_found.create_response(
                        header=(('ETag', target_profile.commit_id, ), ),
                        data={'profile': target_profile.to_dict(), })

                else:
                    if profile_i_follow_opponent_rel or profile_opponent_follows_me_rel\
                       or (profile_opponent_requests_follow_to_me_rel)\
                       or (profile_opponent_blocks_me_rel and profile_i_follow_opponent_rel):
                        return ResourceResponseCase.resource_found.create_response(
                            header=(('ETag', target_profile.commit_id, ), ),
                            data={'profile': target_profile.to_dict(), })

                return ResourceResponseCase.resource_forbidden.create_response(
                    message='해당 프로필을 볼 수 없습니다.')

            # If profile is not private, and opponent blocks me, and I don't follow the opponent,
            # then I cannot see the profile.
            profile_rels = db.session.query(profile_module.ProfileRelation)\
                .filter(
                    sql.or_(
                        sql.and_(
                            profile_module.ProfileRelation.from_profile_id == target_profile.uuid,
                            profile_module.ProfileRelation.to_profile_id == requested_profile_id,
                            profile_module.ProfileRelation.status == profile_module.ProfileRelationStatus.BLOCK, ),
                        sql.and_(
                            profile_module.ProfileRelation.from_profile_id == requested_profile_id,
                            profile_module.ProfileRelation.to_profile_id == target_profile.uuid,
                            profile_module.ProfileRelation.status.in_((
                                profile_module.ProfileRelationStatus.FOLLOW,
                                profile_module.ProfileRelationStatus.HIDE, )), ), )).all()
            if [pr for pr in profile_rels if pr.status == profile_module.ProfileRelationStatus.BLOCK]:
                # If opponent blocks me, and if there's no relationship from me to opponent,
                # then we need to block this.
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='해당 프로필을 볼 수 없습니다.')

            return ResourceResponseCase.resource_found.create_response(
                header=(('ETag', target_profile.commit_id, ), ),
                data={'profile': target_profile.to_dict(), })
        except Exception:
            return CommonResponseCase.server_error.create_response()

    # Modify profile
    @api_class.RequestHeader(
        required_fields={'If-Match': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        optional_fields={
            'name': {'type': 'string', },
            'team_name': {'type': 'string', },
            'description': {'type': 'string', },
            'data': {'type': 'string', },
            'image_url': {'type': 'string', },
            'private': {'type': 'boolean', },
            'can_annonymous_invite': {'type': 'boolean', }, })
    def patch(self, profile_id: int, req_header: dict, req_body: dict, access_token: jwt_module.AccessToken):
        '''
        description: Modify user's {profile_id} profile. This can be done only by the owner.
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

            # Modify this profile
            editable_columns = (
                'name', 'team_name',
                'description', 'data',
                'private', 'can_annonymous_invite')
            filtered_data = {col: field_val for col, field_val in req_body.items() if col in editable_columns}
            if not filtered_data:
                return CommonResponseCase.body_empty.create_response()
            for column, field_val in filtered_data.items():
                result_value = field_val
                if not isinstance(result_value, (bool, int)) and not result_value:
                    result_value = None
                elif isinstance(result_value, (dict, list)):
                    result_value = json.dumps(field_val, ensure_ascii=False)

                setattr(target_profile, column, result_value)

            # We must handle 'data' field specially
            if 'data' in req_body:
                # 'data' field is in req_body. Parse data and modify proper columns
                # We need to get first item in columns
                profile_data: dict[str, dict[str, typing.Any]] = req_body['data']
                filtered_profile_data: dict[str, str] = dict()

                listize_target_fields = ['email', 'phone', 'sns', 'address']
                for field in listize_target_fields:
                    field_data: dict[str, dict[str, typing.Any]] = profile_data.get(field, {'value': None})['value']
                    if not field_data:
                        continue

                    field_data: list[tuple[str, int, str]] = [
                        (k, v['index'], v['value']) for k, v in field_data.items()]
                    field_data.sort(key=lambda i: i[1])
                    field_data = field_data[0]

                    filtered_profile_data[field] = json.dumps({field_data[0]: field_data[2], }, ensure_ascii=False)

                # And set proper values on orm object
                editable_columns = ('email', 'phone', 'sns', 'address')
                filtered_data = {col: data for col, data in filtered_profile_data.items() if col in editable_columns}
                for column, data in filtered_data.items():
                    setattr(target_profile, column, json.dumps(data, ensure_ascii=False))

            # Apply changeset on user db
            with sqs_action.UserDBJournalCreator(db):
                db.session.commit()

            return ResourceResponseCase.resource_modified.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'If-Match': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self, profile_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Delete user's {profile_id} profile. This can be done by admin or the owner.
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
                    message='프로필은 관리자나 해당 명함의 주인만이 삭제할 수 있습니다.')

            # Check Etag
            if target_profile.commit_id != req_header.get('If-Match', None):
                return ResourceResponseCase.resource_prediction_failed.create_response(
                    message='프로필이 다른 기기에서 수정된 것 같습니다.\n동기화를 해 주세요.')

            deleted_at_time = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)

            # Mark this profile as deleted
            target_profile.deleted_at = deleted_at_time
            target_profile.deleted_by_id = access_token.user
            target_profile.why_deleted = 'DELETE_REQUESTED'

            # Delete profile id on user roles. This must be done after create opetaion to get UUID of profile
            current_role: list[typing.Union[str, dict]] = json.loads(target_profile.user.role)
            current_role = [r for r in current_role
                            if ('admin' in r)
                            or (isinstance(r, dict)
                                and r.get('type', '') == 'profile'
                                and r.get('id', '') != target_profile.uuid)
                            or (isinstance(r, dict)
                                and r.get('type', '') != 'profile')]
            target_profile.user.role = json.dumps(current_role, ensure_ascii=False)
            db.session.commit()

            # Revoke access token so that user renews their access token that excludes this profile id
            query_result = db.session.query(jwt_module.RefreshToken)\
                .filter(jwt_module.RefreshToken.user == target_profile.user_id).all()
            if not query_result:
                # How could this happend?
                return AccountResponseCase.access_token_invalid.create_response(
                    message='해당 유저의 로그인 기록을 찾을 수 없습니다.\n이 경우는 일어나면 안되며, 관리자한테 문의해주세요.')

            for target in query_result:
                # TODO: set can set multiple at once, so use that method instead
                redis_key = db_module.RedisKeyType.TOKEN_REVOKE.as_redis_key(target.jti)
                redis_db.set(redis_key, 'revoked', datetime.timedelta(weeks=2))

            # Apply changeset on user db
            with sqs_action.UserDBJournalCreator(db):
                db.session.commit()

            # Profile must leave from the all chat rooms
            chat_participant_records = db.session.query(chat_module.ChatParticipant)\
                .filter(chat_module.ChatParticipant.profile_id == target_profile.uuid)\
                .all()
            target_chatrooms = [(p, p.room) for p in chat_participant_records]
            for participant, room in target_chatrooms:
                room.leave_participant(participant, False)
            db.session.commit()

            return ResourceResponseCase.resource_deleted.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()
