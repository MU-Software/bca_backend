import datetime
import flask
import flask.views
import typing

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.chat as chat_module

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db


class ChatEventRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def get(self, room_id: int,
            req_header: dict,
            access_token: jwt_module.AccessToken,
            event_id: typing.Optional[int] = None):
        '''
        description: Get specific chatroom's event.
        responses:
            - resource_created
            - resource_not_found
            - resource_forbidden
            - server_error
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

            target_chatroom_participant = db.session.query(chat_module.ChatParticipant)\
                .filter(chat_module.ChatParticipant.room_id == target_room.uuid)\
                .filter(chat_module.ChatParticipant.profile_id == requested_profile_id)\
                .first()
            if not target_chatroom_participant:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='현재 해당 채팅방에 입장한 상태가 아닙니다.')

            current_date = utils.as_utctime(datetime.datetime.utcnow()).date()
            one_week_ago = current_date - datetime.timedelta(weeks=1)
            target_event_query = db.session.query(chat_module.ChatEvent)\
                .filter(chat_module.ChatEvent.created_at > one_week_ago)\
                .filter(chat_module.ChatEvent.room_id == target_room.uuid)

            if event_id:
                target_event = target_event_query.filter(chat_module.ChatEvent.uuid == event_id).first()
                if not target_event:
                    return ResourceResponseCase.resource_not_found.create_response(
                        data={'resource_name': ['chat_event', ]})
                return ResourceResponseCase.resource_found.create_response(
                    data={'chat_event': target_event.to_dict(), }, )

            target_events = target_event_query.order_by(chat_module.ChatEvent.uuid).all()
            if not target_events:
                return ResourceResponseCase.resource_not_found.create_response(
                    data={'resource_name': ['chat_event', ]})

            return ResourceResponseCase.multiple_resources_found.create_response(
                data={'chat_events': [e.to_dict() for e in target_events]})

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer'}, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(required_fields={'message': {'type': 'string'}})
    def put(self,
            room_id: int,
            req_header: dict,
            access_token: jwt_module.AccessToken,
            req_body: dict,
            event_id: typing.Optional[int] = None):
        '''
        description: Send message on specific chatroom.
        responses:
            - resource_created
            - resource_not_found
            - resource_forbidden
            - server_error
        '''
        try:
            if event_id:
                return CommonResponseCase.http_not_found.create_response()

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
                    data={'resource_name': ['chat_room', ], }, )

            target_participant = db.session.query(chat_module.ChatParticipant)\
                .filter(chat_module.ChatParticipant.room_id == room_id)\
                .filter(chat_module.ChatParticipant.profile_id == requested_profile_id)\
                .first()
            if not target_participant:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='방에 참가한 상태가 아닙니다.')

            new_event = target_room.create_new_event(
                chat_module.ChatEventType.MESSAGE_POSTED,
                target_participant, req_body['message'], True)

            return ResourceResponseCase.resource_created.create_response(data={'chat_event': new_event.to_dict(), }, )

        except Exception:
            return CommonResponseCase.server_error.create_response()
