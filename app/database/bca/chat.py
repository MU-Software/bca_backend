import datetime
import enum

import app.common.utils as utils
import app.common.firebase_notify as fcm_module
import app.database as db_module
import app.database.user as user_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module

db = db_module.db


class ChatEventType(utils.EnumAutoName):
    PARTICIPANT_IN = enum.auto()
    PARTICIPANT_OUT = enum.auto()
    PARTICIPANT_KICKED = enum.auto()

    MESSAGE_POSTED = enum.auto()
    MESSAGE_POSTED_IMAGE = enum.auto()
    MESSAGE_DELETED = enum.auto()


event_message_kor = {
    ChatEventType.PARTICIPANT_IN: '{name}님이 들어왔습니다.',
    ChatEventType.PARTICIPANT_OUT: '{name}님이 나가셨습니다.',
    ChatEventType.PARTICIPANT_KICKED: '{name}님이 내보내졌습니다.',

    ChatEventType.MESSAGE_POSTED: '',
    ChatEventType.MESSAGE_POSTED_IMAGE: '',
    ChatEventType.MESSAGE_DELETED: '메시지가 삭제되었습니다.',
}


class ChatRoom(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_CHAT_ROOM'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_ChatRoom_UUID'),
                     primary_key=True,
                     nullable=False)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=True)

    created_by_user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    created_by_user: user_module.User = db.relationship(
                                            'User',
                                            primaryjoin=created_by_user_id == user_module.User.uuid)
    created_by_profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    created_by_profile: profile_module.Profile = db.relationship(
                                            'Profile',
                                            primaryjoin=created_by_profile_id == profile_module.Profile.uuid)

    participant_count = db.Column(db.Integer, nullable=False, default=0)
    participants: list['ChatParticipant'] = None  # Placeholder for backref

    deleted_at = db.Column(db.DateTime, nullable=True)
    locked = db.Column(db.Boolean, nullable=False, default=False)
    private = db.Column(db.Boolean, nullable=False, default=True)  # Placeholder for future update
    encrypted = db.Column(db.Boolean, nullable=False, default=False)  # Placeholder for future update

    def add_new_participant(self, profile: profile_module.Profile, db_commit: bool = False):
        new_participant = ChatParticipant()
        new_participant.room = self
        new_participant.room_name = self.name

        new_participant.user_id = profile.user_id
        new_participant.profile_id = profile.uuid
        new_participant.profile_name = profile.name

        self.participant_count += 1

        db.session.add(new_participant)
        db.session.commit()

        self.create_new_event(ChatEventType.PARTICIPANT_IN, new_participant, db_commit=db_commit)

    def leave_participant(self, participant: 'ChatParticipant', db_commit: bool = False):
        db.session.delete(participant)
        self.participant_count -= 1

        self.create_new_event(ChatEventType.PARTICIPANT_OUT, participant, db_commit=False)

        if not self.participant_count:
            self.deleted_at = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)

        if db_commit:
            db.session.commit()

    def send_message(self, participant: 'ChatParticipant', message: str, db_commit: bool = False):
        message = utils.normalize(message)
        self.create_new_event(ChatEventType.MESSAGE_POSTED, participant, message, db_commit=db_commit)

    def create_new_event(self,
                         event_type: 'ChatEventType',
                         caused_by_participant: 'ChatParticipant',
                         message: str = None,
                         db_commit: bool = False) -> 'ChatEvent':
        latest_event = db.session.query(ChatEvent)\
            .filter(ChatEvent.room_id == self.uuid)\
            .order_by(ChatEvent.event_index.desc()).first()

        new_event = ChatEvent()
        new_event.room = self
        new_event.event_index = latest_event.event_index + 1 if latest_event else 0
        new_event.event_type = event_type.value
        if message and event_type in (ChatEventType.MESSAGE_POSTED, ChatEventType.MESSAGE_POSTED_IMAGE, ):
            new_event.message = message
        else:
            new_event.message = event_message_kor[event_type].format(**caused_by_participant.profile.to_dict())

        new_event.caused_by_user_id = caused_by_participant.user_id
        new_event.caused_by_profile_id = caused_by_participant.profile_id
        new_event.caused_by_participant_id = caused_by_participant.uuid

        db.session.add(new_event)

        if db_commit:
            db.session.commit()

        # Send FCM push to all chat participants here
        # Set send target and send this messages to all, including event-raised users
        target_users: set[int] = {participant.user_id for participant in self.participants}
        target_users_fcm_tokens: list[str] = db.session.query(jwt_module.RefreshToken.client_token)\
            .filter(jwt_module.RefreshToken.user.in_(target_users)).distinct().all()
        target_fcm_tokens = [tk for tk in target_users_fcm_tokens if tk]
        fcm_data = new_event.to_dict()
        if new_event.event_type == ChatEventType.MESSAGE_POSTED:
            fcm_data['title'] = self.name
            fcm_data['message'] = new_event.message

        try:
            fcm_module.firebase_send_notify(
                title=fcm_data.get('title', None),
                body=fcm_data('message', None),
                data=fcm_data,
                target_tokens=target_fcm_tokens)
        except Exception:
            pass

        return new_event

    def to_dict(self, include_events: bool = False):
        result_dict = {
            'resource': 'chat_room',

            'uuid': self.uuid,
            'name': self.name,
            'description': self.description,
            'participant_count': self.participant_count,
            'owner_profile_id': self.owner_profile_id,
            'owner_profile': self.owner_profile.to_dict(),

            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'modified': self.created_at != self.modified_at,
            'commit_id': self.commit_id,
        }

        if self.participants:
            result_dict['participants'] = list()
            for participant in self.participants:
                result_dict['participants'].append(participant.to_dict())

        if include_events:
            query_limit_time = datetime.datetime.utcnow().replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
                tzinfo=utils.UTC, ) - datetime.timedelta(days=7)

            chatroom_events = db.session.query(ChatEvent)\
                .filter(ChatEvent.room_id == self.uuid)\
                .filter(ChatEvent.created_at >= query_limit_time)\
                .all()
            if chatroom_events:
                result_dict['events'] = list()
                for event in chatroom_events:
                    result_dict['events'].append(event.to_dict())

        return result_dict


class ChatParticipant(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_CHAT_PARTICIPANT'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_ChatParticipant_UUID'),
                     primary_key=True,
                     nullable=False)

    room_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_CHAT_ROOM.uuid'), nullable=False)
    room: ChatRoom = db.relationship('ChatRoom',
                                     primaryjoin=room_id == ChatRoom.uuid,
                                     backref=db.backref('participants',
                                                        order_by='ChatParticipant.user_id.desc()'))

    # User-set room name
    room_name = db.Column(db.String, nullable=True)
    # User-set profile name in this room
    profile_name = db.Column(db.String, nullable=True)

    # Unnormalize for the fast query
    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    user: user_module.User = db.relationship('User', primaryjoin=user_id == user_module.User.uuid)
    profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    profile: profile_module.Profile = db.relationship('Profile', primaryjoin=profile_id == profile_module.Profile.uuid)

    def to_dict(self):
        return {
            'resource': 'chat_participant',

            'uuid': self.uuid,
            'room_id': self.room_id,
            'room_name': self.room_name,

            'profile_id': self.profile_id,
            'profile_name': self.profile_name,
            'profile_info': self.profile.to_dict(),

            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'modified': self.created_at != self.modified_at,
            'commit_id': self.commit_id,
        }


class ChatEvent(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_CHAT_EVENT'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_ChatMessage_UUID'),
                     primary_key=True,
                     nullable=False)
    event_index = db.Column(db.Integer, nullable=False)
    event_type = db.Column(db.String, nullable=False)
    message = db.Column(db.String, nullable=False)

    room_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_CHAT_ROOM.uuid'), nullable=False)
    room: ChatRoom = db.relationship('ChatRoom', primaryjoin=room_id == ChatRoom.uuid)

    # Unnormalize for the fast query
    caused_by_user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    caused_by_user: user_module.User = db.relationship(
                                            'User',
                                            primaryjoin=caused_by_user_id == user_module.User.uuid)
    caused_by_profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    caused_by_profile: profile_module.Profile = db.relationship(
                                                    'Profile',
                                                    primaryjoin=caused_by_profile_id == profile_module.Profile.uuid)
    caused_by_participant_id = db.Column(db_module.PrimaryKeyType,
                                         db.ForeignKey('TB_CHAT_PARTICIPANT.uuid'),
                                         nullable=False)
    caused_by_participant: ChatParticipant = db.relationship(
                                                'ChatParticipant',
                                                primaryjoin=caused_by_participant_id == ChatParticipant.uuid)

    encrypted = db.Column(db.Boolean, nullable=False, default=False)  # Placeholder for future update

    def to_dict(self):
        return {
            'resource': 'chat_event',
            'uuid': self.uuid,

            'room_id': self.room_id,
            'caused_by_profile_id': self.caused_by_profile_id,
            'caused_by_participant_id': self.caused_by_participant_id,
            'encrypted': self.encrypted,

            'event_index': self.event_index,
            'event_type': self.event_type,
            'message': self.message,

            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'modified': self.created_at != self.modified_at,
            'commit_id': self.commit_id,
        }
