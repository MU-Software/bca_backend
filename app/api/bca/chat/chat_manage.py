import flask
import flask.views
import typing

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module
import app.database.bca.chat as chat_module

import app.api.bca.chat.helper.chat_invitation as chat_invitation

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db


class ChatManageRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        optional_fields={'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def get(self, room_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Get this chatroom information.
            If requested user is in this chatroom, then returns detailed information of this room.
        responses:
            - resource_created
            - resource_forbidden
            - resource_not_found
            - resource_conflict
        '''
        try:
            target_room = db.session.query(chat_module.ChatRoom)\
                .filter(chat_module.ChatRoom.deleted_at.is_(None))\
                .filter(chat_module.ChatRoom.uuid == room_id)\
                .first()
            if not target_room:
                return ResourceResponseCase.resource_not_found.create_response(
                    data={'resource_name': ['chat_room', ]})

            requested_profile_id: typing.Optional[int] = req_header.get('X-Profile-Id', None)
            is_user_in_room = db.session.query(chat_module.ChatParticipant)\
                .filter(chat_module.ChatParticipant.room_id == room_id)\
                .filter(chat_module.ChatParticipant.user_id == access_token.user)\
                .all()
            if not is_user_in_room and target_room.private:
                return ResourceResponseCase.resource_forbidden.create_response(message='공개되어 있지 않은 방입니다.', )

            is_profile_in_room = bool([p for p in is_user_in_room if p.profile_id == requested_profile_id])
            result_data = target_room.to_dict(is_profile_in_room is not None)
            result_data['is_profile_entered'] = is_profile_in_room
            return ResourceResponseCase.resource_found.create_response(data={'chat_room': result_data, }, )

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(required_fields={'inviting_profiles': {'type': 'string'}}, )
    def put(self, room_id: int, req_header: dict, access_token: jwt_module.AccessToken, req_body: dict):
        '''
        description: Enter this chatroom. If requested user is on this chatroom,
            and req user sent another user's profile id, then invite that user.
        responses:
            - resource_created
            - multiple_resources_found
            - resource_forbidden
            - resource_not_found
            - resource_conflict
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

            target_profiles_id_str: str = req_body.get('inviting_profiles', 'null')
            target_profiles_id_list: typing.Union[int, str, list[int], None] =\
                utils.safe_json_loads(target_profiles_id_str)
            if not target_profiles_id_list:
                return CommonResponseCase.body_invalid.create_response(
                    message='잘못된 요청입니다.\n(요청하신 초대할 프로필 목록이 비어있거나 이해할 수 없습니다.)')
            elif isinstance(target_profiles_id_list, list):
                # Check all elements in list is int
                if all([isinstance(e, int) for e in target_profiles_id_list]):
                    return CommonResponseCase.body_invalid.create_response(
                        message='잘못된 요청입니다.\n(요청하신 초대할 프로필 목록 내 항목의 타입이 잘못되었습니다.)')
            elif isinstance(target_profiles_id_list, (int, str)):
                target_profiles_id_list = utils.safe_int(target_profiles_id_list)
                if not target_profiles_id_list:
                    return CommonResponseCase.body_invalid.create_response(
                        message='잘못된 요청입니다.\n(요청하신 초대할 프로필 ID의 타입이 잘못되었습니다.)')
                target_profiles_id_list = [target_profiles_id_list, ]
            else:
                return CommonResponseCase.body_invalid.create_response(
                    message='잘못된 요청입니다.\n(요청하신 초대할 프로필 목록의 형태가 잘못되었습니다.)')

            target_room = db.session.query(chat_module.ChatRoom)\
                .filter(chat_module.ChatRoom.deleted_at.is_(None))\
                .filter(chat_module.ChatRoom.uuid == room_id)\
                .first()
            if not target_room:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='해당 채팅방을 찾을 수 없습니다.',
                    data={'resource_name': ['chat_room', ]})

            target_profiles = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .filter(profile_module.Profile.uuid.in_(target_profiles_id_list))\
                .all()
            if not target_profiles:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='해당 프로필들을 찾을 수 없습니다.',
                    data={'resource_name': ['profile', ]})
            if len(target_profiles_id_list) != 1 and [p for p in target_profiles if p.user_id == access_token.user]:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='본인의 프로필을 다른 프로필들과 함께 초대할 수 없습니다.')

            result: list[chat_invitation.ChatInvitableCheckReturnType] = list()
            for target_profile in target_profiles:
                result.append(chat_invitation.is_profile_chat_invitable(
                    requested_profile_id=requested_profile_id,
                    requested_user_id=access_token.user,
                    target_room=target_room,
                    target_profile=target_profile,
                    check_is_user_in_room=True,
                    db_commit=True))

            # If all profiles were failed to invite
            if all(map(lambda x: not x.success, result)):
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='요청하신 모든 프로필들을 초대할 수 없었습니다.')
            # If we succeed to invite all profiles
            elif all(map(lambda x: x.success, result)):
                return ResourceResponseCase.resource_created.create_response(
                    message='모든 프로필을 초대했습니다.')
            # If we failed to invite some profiles
            else:
                response_data = {k: v for k, b, v in map(
                    lambda p: (
                        p.profile_id,
                        p.success,
                        {'code': p.code, 'message': p.message, 'data': p.data}
                    ), result) if b}
                return ResourceResponseCase.multiple_resources_found.create_response(
                    message='몇몇 프로필은 초대에 실패했습니다.',
                    data={'reason': response_data})

        except Exception:
            return CommonResponseCase.server_error.create_response(
                message='서버에 문제가 발생했습니다,\n10분 후에 다시 시도해주세요.')

    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        optional_fields={
            'owner_profile_id': {'type': 'integer'},
            'name': {'type': 'string'},
            'description': {'type': 'string'},
            'private': {'type': 'boolean'}, }, )
    def patch(self, room_id: int, req_header: dict, access_token: jwt_module.AccessToken, req_body: dict):
        '''
        description: Modify this chatroom information. This can be done only by the owner of this room.
        responses:
            - resource_modified
            - resource_forbidden
            - resource_not_found
            - body_empty
            - body_bad_semantics
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

            target_room = db.session.query(chat_module.ChatRoom)\
                .filter(chat_module.ChatRoom.deleted_at.is_(None))\
                .filter(chat_module.ChatRoom.uuid == room_id)\
                .first()
            if not target_room:
                return ResourceResponseCase.resource_not_found.create_response(
                    data={'resource_name': ['chat_room', ]})
            if target_room.owner_profile_id != requested_profile_id:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='방 정보는 방을 소유한 프로필만이 수정할 수 있습니다.')

            # Modify this chatroom information
            editable_columns = ('owner_profile_id', 'name', 'description', 'private', )
            filtered_data = {col: data for col, data in req_body.items() if col in editable_columns}
            if not filtered_data:
                return CommonResponseCase.body_empty.create_response()
            if 'owner_profile_id' in filtered_data:
                if len(filtered_data) != 1:
                    return CommonResponseCase.body_bad_semantics.create_response(
                        data={'bad_semantics': [{
                            'field': 'owner_profile_id',
                            'reason': '권한을 이양할 시에는 방의 다른 정보를 수정할 수 없습니다.'}, ], }, )

                # Check if owner_profile_id profile exists and it's entered in this room.
                new_owner_profile = db.session.query(profile_module.Profile)\
                    .filter(profile_module.Profile.deleted_at.is_(None))\
                    .filter(profile_module.Profile.locked_at.is_(None))\
                    .filter(profile_module.Profile.uuid == filtered_data['owner_profile_id'])\
                    .first()
                if not new_owner_profile:
                    return ResourceResponseCase.resource_not_found.create_response()

                is_new_owner_participant = db.session.query(chat_module.ChatParticipant)\
                    .filter(chat_module.ChatParticipant.room_id == target_room.uuid)\
                    .filter(chat_module.ChatParticipant.user_id == new_owner_profile.user_id)\
                    .filter(chat_module.ChatParticipant.profile_id == new_owner_profile.uuid)\
                    .first()
                if not is_new_owner_participant:
                    return ResourceResponseCase.resource_forbidden.create_response(
                        message='권한을 이양할 프로필이 방에 참가하고 있지 않습니다.')

                target_room.owner_user_id = new_owner_profile.user_id
                target_room.owner_profile_id = new_owner_profile.uuid
                return ResourceResponseCase.resource_modified.create_response(data=target_room.to_dict(False))

            for column, data in filtered_data.items():
                setattr(target_room, column, data)

            db.session.commit()
            return ResourceResponseCase.resource_modified.create_response(data=target_room.to_dict(True))

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self, room_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Leave this chatroom. If there was only me on this chatroom, then remove this room, too.
        responses:
            - resource_deleted
            - resource_forbidden
            - resource_not_found
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

            target_room = db.session.query(chat_module.ChatRoom)\
                .filter(chat_module.ChatRoom.deleted_at.is_(None))\
                .filter(chat_module.ChatRoom.uuid == room_id)\
                .first()
            if not target_room:
                return ResourceResponseCase.resource_not_found.create_response(
                    data={'resource_name': ['chat_room', ]})

            requested_participant = db.session.query(chat_module.ChatParticipant)\
                .filter(chat_module.ChatParticipant.room_id == target_room.uuid)\
                .filter(chat_module.ChatParticipant.profile_id == requested_profile_id)\
                .first()
            if not requested_participant:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='이 방에 속해있지 않습니다.')

            target_room.leave_participant(requested_participant, True)
            return ResourceResponseCase.resource_deleted.create_response()

        except Exception:
            return CommonResponseCase.server_error.create_response()
