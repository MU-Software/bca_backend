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

    latest_message_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_CHAT_EVENT.uuid'), nullable=True)
    latest_message: 'ChatEvent' = db.relationship(
                                        'ChatEvent',
                                        primaryjoin='ChatRoom.latest_message_id == ChatEvent.uuid')
    latest_event_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_CHAT_EVENT.uuid'), nullable=True)
    latest_event: 'ChatEvent' = db.relationship(
                                        'ChatEvent',
                                        primaryjoin='ChatRoom.latest_event_id == ChatEvent.uuid')

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

        new_participant.last_read_message_id = self.latest_message_id
        db.session.add(new_participant)

        self.create_new_event(ChatEventType.PARTICIPANT_IN, new_participant, db_commit=db_commit)

    def leave_participant(self, participant: 'ChatParticipant', db_commit: bool = False):
        db.session.delete(participant)
        self.create_new_event(ChatEventType.PARTICIPANT_OUT, participant, db_commit=False)

        if not self.participants:
            self.deleted_at = datetime.datetime.utcnow().replace(tz=utils.UTC)

        if db_commit:
            db.session.commit()

    def send_message(self, participant: 'ChatParticipant', message: str, db_commit: bool = False):
        message = utils.normalize(message)
        self.create_new_event(ChatEventType.MESSAGE_POSTED, participant, message, db_commit=db_commit)

    def create_new_event(self,
                         event_type: 'ChatEventType',
                         caused_by_participant: 'ChatParticipant',
                         message: str = None,
                         db_commit: bool = False):
        new_event = ChatEvent()
        new_event.room = self
        new_event.event_index = self.latest_event.event_index + 1
        new_event.event_type = event_type
        if message and event_type in (ChatEventType.MESSAGE_POSTED, ChatEventType.MESSAGE_POSTED_IMAGE, ):
            new_event.message = message
        else:
            new_event.message = event_message_kor[event_type].format(caused_by_participant.profile.to_dict())

        new_event.caused_by_user_id = caused_by_participant.user_id
        new_event.caused_by_profile_id = caused_by_participant.profile_id
        new_event.caused_by_participant = caused_by_participant

        db.session.add(new_event)

        self.latest_event = new_event
        if event_type in (ChatEventType.MESSAGE_POSTED, ChatEventType.MESSAGE_POSTED_IMAGE, ):
            self.latest_message = new_event

        # Send FCM push to all chat participants here
        # Set send target and send this messages to all, including event-raised users
        target_users: set[int] = {participant.user_id for participant in self.participants}
        target_users_refreshtokens = db.session.query(jwt_module.RefreshToken)\
            .filter(jwt_module.RefreshToken.user.in_(target_users))\
            .all()
        for refresh_token in target_users_refreshtokens:
            if refresh_token.client_token:
                try:
                    title, body = None, None
                    if new_event.event_type == ChatEventType.MESSAGE_POSTED:
                        title, body = self.name, new_event.message
                    fcm_module.firebase_send_notify(
                        title=title, body=body, data=new_event.to_dict(),
                        target_token=refresh_token.client_token)
                except Exception as err:
                    print(utils.get_traceback_msg(err))

        if db_commit:
            db.session.commit()

    def to_dict(self, detailed: bool = False):
        result_dict = {
            'resource': 'chat_room',

            'uuid': self.uuid,
            'name': self.name,
            'description': self.description,
            'participant_num': len(self.participants),
            'created_by_profile_id': self.created_by_profile_id,
            'created_by_profile': self.created_by_profile.to_dict(),
        }

        if detailed:
            result_dict.update({
                'latest_message_id': self.latest_message_id,
                'latest_message_text': self.latest_message.message if self.latest_message else '',
                'latest_event_id': self.latest_event_id,
                'latest_event': self.latest_event.to_dict(), }, )

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
    room_name = db.Column(db.String, nullable=False)
    # User-set profile name in this room
    profile_name = db.Column(db.String, nullable=False)

    # Unnormalize for the fast query
    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    user: user_module.User = db.relationship('User', primaryjoin=user_id == user_module.User.uuid)
    profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    profile: profile_module.Profile = db.relationship('Profile', primaryjoin=profile_id == profile_module.Profile.uuid)

    # For the message read count support
    last_read_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    last_read_message_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_CHAT_EVENT.uuid'), nullable=True)

    def to_dict(self):
        return {
            'resource': 'chat_participant',

            'uuid': self.uuid,
            'room_id': self.room_id,
            'room_name': self.room_name,

            'profile_id': self.profile_id,
            'profile_name': self.profile_name,
            'profile_info': self.profile.to_dict(),

            'last_read_at': self.last_read_at,
            'last_read_message_id': self.last_read_message_id,
        }


class ChatEvent(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_CHAT_EVENT'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_ChatMessage_UUID'),
                     primary_key=True,
                     nullable=False)
    event_index = db.Column(db_module.PrimaryKeyType, nullable=False)
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
            'encrypted': self.encrypted,

            'event_index': self.event_index,
            'event_type': self.event_type,
            'message': self.message,
        }
