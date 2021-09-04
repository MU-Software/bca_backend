import app.database as db_module
import app.database.user as user_module
import app.database.bca.profile as profile_module

db = db_module.db


class ChatRoom(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_CHAT_ROOM'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_ChatRoom_UUID'),
                     primary_key=True,
                     nullable=False)
    name = db.Column(db.String, nullable=False)

    created_by_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    created_by: profile_module.Profile = db.relationship('Profile',
                                                         primaryjoin=created_by_id == profile_module.Profile.uuid)

    latest_message_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_CHAT_MESSAGE.uuid'), nullable=True)
    latest_message: 'ChatMessage' = db.relationship(
                                        'ChatMessage',
                                        primaryjoin='TB_CHAT_ROOM.latest_message_id = TB_CHAT_ROOM.uuid')

    private = db.Column(db.Boolean, nullable=False, default=True)  # Placeholder for future update
    encrypted = db.Column(db.Boolean, nullable=False, default=False)  # Placeholder for future update


class ChatParticipant(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_CHAT_PARTICIPANT'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_ChatParticipant_UUID'),
                     primary_key=True,
                     nullable=False)

    room_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_CHAT_ROOM.uuid'), nullable=False)
    room: ChatRoom = db.relationship('ChatRoom', primaryjoin=room_id == ChatRoom.uuid)

    # Unnormalize for the fast query
    profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    profile: profile_module.Profile = db.relationship('Profile', primaryjoin=profile_id == profile_module.Profile.uuid)
    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    user: user_module.User = db.relationship('User', primaryjoin=user_id == user_module.User.uuid)

    # For the message read count support
    last_read_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    last_read_message_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_CHAT_MESSAGE.uuid'), nullable=False)


class ChatMessage(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_CHAT_MESSAGE'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_ChatMessage_UUID'),
                     primary_key=True,
                     nullable=False)
    message = db.Column(db.String, nullable=False)

    room_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_CHAT_ROOM.uuid'), nullable=False)
    room: ChatRoom = db.relationship('ChatRoom', primaryjoin=room_id == ChatRoom.uuid)

    # Unnormalize for the fast query
    profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    profile: profile_module.Profile = db.relationship('Profile',
                                                      primaryjoin=profile_id == profile_module.Profile.uuid,
                                                      backref=db.backref('chat_messages',
                                                                         order_by='ChatRoom.created_at.desc()'))
    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    user: user_module.User = db.relationship('User',
                                             primaryjoin=user_id == user_module.User.uuid,
                                             backref=db.backref('chats',
                                                                order_by='ChatRoom.created_at.desc()'))

    encrypted = db.Column(db.Boolean, nullable=False, default=False)  # Placeholder for future update
