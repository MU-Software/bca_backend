import flask
import flask.views
import sqlalchemy as sql
import sqlalchemy.sql as sql_sql
import json

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module
import app.database.bca.chat as chat_module

import app.api.bca.chat.helper.chat_invitation as chat_invitation

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db


class ChatRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def get(self, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Returns chatrooms' information that this profile participants.
        responses:
            - multiple_resources_found
            - resource_forbidden
            - resource_not_found
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

            participanted_chatroom_id_query = db.session.query(chat_module.ChatParticipant.room_id)\
                .filter(chat_module.ChatParticipant.profile_id == requested_profile_id)\
                .distinct()
            participanted_chatroom = db.session.query(chat_module.ChatRoom)\
                .filter(chat_module.ChatRoom.uuid.in_(participanted_chatroom_id_query))\
                .all()
            if not participanted_chatroom:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='참여 중인 채팅방이 없습니다.')

            return ResourceResponseCase.multiple_resources_found.create_response(
                data={'chat_rooms': [r.to_dict(include_events=True) for r in participanted_chatroom], }, )

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        required_fields={'inviting_profiles': {'type': 'string'}, },
        optional_fields={
            'name': {'type': 'string'},
            'description': {'type': 'string'},
            'private': {'type': 'boolean'}, }, )
    def post(self, req_header: dict, access_token: jwt_module.AccessToken, req_body: dict):
        '''
        description: Create chatroom.
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

            requested_profile = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .filter(profile_module.Profile.uuid == requested_profile_id)\
                .first()
            if not requested_profile:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='요청하신 프로필이 존재하지 않습니다.')

            # Try to invite other profiles
            # Parse chatroom profile list on request body
            try:
                target_profiles_id_str = req_body['inviting_profiles']
                if not target_profiles_id_str:
                    return CommonResponseCase.body_empty.create_response(
                        message='잘못된 요청입니다.\n(요청이 비어있습니다.)')

                target_profiles_id_list: list[int] = json.loads(target_profiles_id_str)
                if not target_profiles_id_list:
                    return CommonResponseCase.body_invalid.create_response(
                        message='잘못된 요청입니다.\n(요청하신 초대할 프로필 목록이 비어있습니다.)')
                elif isinstance(target_profiles_id_list, (int, str)):
                    target_profiles_id_list = [int(target_profiles_id_list), ]
                elif not isinstance(target_profiles_id_list, (list, int, str)):
                    return CommonResponseCase.body_invalid.create_response(
                        message='잘못된 요청입니다.\n(요청하신 초대할 프로필 목록의 형태가 잘못되었습니다.)')
            except Exception:
                # Parsing 'inviting_profiles' field in request body failed
                return CommonResponseCase.body_invalid.create_response(
                    message='잘못된 요청입니다.\n(요청하신 초대할 프로필 목록을 이해할 수 없습니다.)')

            # If there's already on 1:1 chatroom,
            # then we need to send that room id, rather than creating new room.
            if len(target_profiles_id_list) == 1:
                # We can get room id by using this strategy.
                # TODO: This query isn't working. FIX THIS
                # TODO: This query might be slow, need to be optimized
                distinct_room_id_query = sql.distinct(chat_module.ChatParticipant.room_id)
                queried_room_id = db.session.query(distinct_room_id_query)\
                    .filter(
                        chat_module.ChatParticipant.user_id.in_((
                            target_profiles_id_list[0],
                            requested_profile_id, )))\
                    .having(sql_sql.func.count(distinct_room_id_query) == 2).first()
                if queried_room_id:
                    target_room = db.session.query(chat_module.ChatRoom)\
                        .filter(chat_module.ChatRoom.uuid == queried_room_id).first()
                    return ResourceResponseCase.resource_conflict.create_response(
                        message='이미 1:1 채팅방이 존재합니다.', data={'room': target_room.to_dict(), }, )

            new_chatroom = chat_module.ChatRoom()
            new_chatroom.name = req_body.get('name', '새 채팅방')
            new_chatroom.description = req_body.get('description', None)
            new_chatroom.created_by_user_id = access_token.user
            new_chatroom.created_by_profile_id = requested_profile.uuid
            db.session.add(new_chatroom)

            creator_as_participant = chat_module.ChatParticipant()
            creator_as_participant.room = new_chatroom
            creator_as_participant.user_id = access_token.user
            creator_as_participant.profile_id = requested_profile.uuid
            creator_as_participant.profile_name = requested_profile.name
            db.session.add(creator_as_participant)

            db.session.commit()

            target_profiles = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .filter(profile_module.Profile.uuid.in_(target_profiles_id_list))\
                .all()
            if not target_profiles:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='해당 프로필들을 찾을 수 없습니다.',
                    data={'resource_name': ['profile', ]})
            if len(target_profiles_id_list) != 1 and [p for p in target_profiles
                                                      if p.user_id == access_token.user
                                                      and p.uuid != requested_profile_id]:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='본인의 다른 프로필을 초대할 수 없습니다.')

            result: list[chat_invitation.ChatInvitableCheckReturnType] = list()
            for target_profile in target_profiles:
                result.append(chat_invitation.is_profile_chat_invitable(
                    requested_profile_id=requested_profile_id,
                    requested_user_id=access_token.user,
                    target_room=new_chatroom,
                    target_profile=target_profile,
                    check_is_user_in_room=False,
                    db_commit=True))

            # If all profiles were failed to invite
            if all(map(lambda x: not x.success, result)):
                db.session.delete(creator_as_participant)
                db.session.delete(new_chatroom)
                db.session.commit()
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='요청하신 모든 프로필들을 초대할 수 없었습니다.')

            # If we succeed to invite some profiles, then change name of chatroom to profile names
            if req_body.get('name', False):
                invite_succeed_profiles = [p.name for p in target_profiles
                                           if p.uuid in [z.profile_id for z in result if z.success]]
                new_chatroom.name = ', '.join(invite_succeed_profiles)
                new_chatroom.name = new_chatroom.name if len(new_chatroom.name) < 30 else new_chatroom.name[:28] + '...'
                db.session.commit()

            # If we succeed to invite all profiles
            if all(map(lambda x: x.success, result)):
                return ResourceResponseCase.resource_created.create_response(
                    message='모든 프로필을 초대했습니다.',
                    data={'chat_room': new_chatroom.to_dict()})
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
                    data={
                        'chat_room': new_chatroom.to_dict(),
                        'reason': response_data,
                    }, )

        except Exception:
            return CommonResponseCase.server_error.create_response()
