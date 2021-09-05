import datetime
import typing

import app.common.utils as utils
import app.database as db_module
import app.database.user as user_module
import app.database.board as board_module

db = db_module.db


class Profile(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_PROFILE'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_Profile_UUID'),
                     primary_key=True,
                     nullable=False)

    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    user: user_module.User = db.relationship('User',
                                             primaryjoin=user_id == user_module.User.uuid,
                                             backref=db.backref('profiles',
                                                                order_by='Profile.created_at.desc()'))

    name = db.Column(db.String, nullable=False)  # Profile name shown in card
    description = db.Column(db.String, nullable=True)  # Profile description
    data = db.Column(db.String, nullable=True)  # Profile data (in json)
    email = db.Column(db.String, nullable=True)  # Main email of Profile
    phone = db.Column(db.String, nullable=True)  # Main phone of Profile
    sns = db.Column(db.String, nullable=True)  # Main SNS Account of profile

    cards: list['Card'] = None  # Backref of Card

    # if the profile locked, then anyone cannot access, and this must not be shown on list.
    # This looks quite same as deleted, but...
    #   - profile will be removed on all user's SQLITE DB
    #   - cannot be garbage collected
    #   - cannot recover by admin
    #   - only can be accessed by DB manager
    locked_at: datetime.datetime = db.Column(db.DateTime, nullable=True)
    why_locked = db.Column(db.String, nullable=True)
    locked_by_id = db.Column(db_module.PrimaryKeyType,
                             db.ForeignKey('TB_USER.uuid'),
                             nullable=True)
    locked_by = db.relationship(user_module.User, primaryjoin=locked_by_id == user_module.User.uuid)

    deleted_at: datetime.datetime = db.Column(db.DateTime, nullable=True)
    why_deleted = db.Column(db.String, nullable=True)
    deleted_by_id = db.Column(db_module.PrimaryKeyType,
                              db.ForeignKey('TB_USER.uuid'),
                              nullable=True)
    deleted_by = db.relationship(user_module.User, primaryjoin=deleted_by_id == user_module.User.uuid)

    private = db.Column(db.Boolean, default=False, nullable=False)
    modifiable = db.Column(db.Boolean, default=True, nullable=False)

    is_follower_list_public = db.Column(db.Boolean, default=False, nullable=False)
    is_following_list_public = db.Column(db.Boolean, default=False, nullable=False)

    guestbook: board_module.Board = None  # Placeholder for backref
    announcement: board_module.Board = None  # Placeholder for backref

    def to_dict(self):
        result = {
            'resource': 'profile',

            'uuid': self.uuid,
            'name': self.name,
            'description': self.description,
            'phone': self.phone,
            'email': self.email,
            'sns': self.sns,
            'data': self.data,

            'is_private': self.private,

            'created_at': self.created_at,
            'modified': self.created_at != self.modified_at,
            'modified_at': self.modified_at,
        }

        return result


class ProfileFollow(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_PROFILE_FOLLOW'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_Profile_UUID'),
                     primary_key=True,
                     nullable=False)

    profile_1_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    profile_1: Profile = db.relationship('Profile', primaryjoin=profile_1_id == Profile.uuid)
    user_1_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    user_1: user_module.User = db.relationship('User', primaryjoin=user_1_id == user_module.User.uuid)

    profile_2_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    profile_2: Profile = db.relationship('Profile', primaryjoin=profile_2_id == Profile.uuid)
    user_2_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    user_2: user_module.User = db.relationship('User', primaryjoin=user_2_id == user_module.User.uuid)

    when_1_followed_2 = db.Column(db.DateTime, nullable=True)
    when_2_followed_1 = db.Column(db.DateTime, nullable=True)

    subscripted_cards: list['CardSubscription'] = None

    def get_relation_explain(self) -> dict[tuple[int, int]: bool]:
        '''{(A, B): True} => A IS following B'''
        return {
            (self.profile_1_id, self.profile_2_id): self.when_1_followed_2,
            (self.profile_2_id, self.profile_1_id): self.when_2_followed_1,
        }

    def mark_as_follow(self, follow_requester_id: int, db_commit: bool = False):
        if self.profile_1_id == follow_requester_id:
            if not self.when_1_followed_2:
                self.when_1_followed_2 = datetime.datetime.utcnow().replace(tz=utils.UTC)
        else:
            if not self.when_2_followed_1:
                self.when_2_followed_1 = datetime.datetime.utcnow().replace(tz=utils.UTC)

        if db_commit:
            db.session.commit()

    def mark_as_unfollow(self, unfollow_requester_id: int, db_commit: bool = False):
        if self.profile_1_id == unfollow_requester_id:
            if self.when_1_followed_2:
                self.when_1_followed_2 = None
        else:
            if self.when_2_followed_1:
                self.when_2_followed_1 = None

        if db_commit:
            db.session.commit()

    def to_dict_perspective_of(self, requester_id: int):
        is_requester_profile_1 = requester_id == self.profile_1_id
        result_target_id: int = self.profile_2_id if is_requester_profile_1 else self.profile_1_id
        result_target_following: typing.Optional[datetime.datetime] = self.when_1_followed_2 if is_requester_profile_1\
            else self.when_2_followed_1
        return {result_target_id: result_target_following or False}

    def to_dict_reverse_perspective_of(self, requester_id: int):
        is_requester_profile_1 = requester_id == self.profile_1_id
        reverse_requester_id: int = self.profile_2_id if is_requester_profile_1 else self.profile_1_id
        return self.to_dict_perspective_of(reverse_requester_id)


class Card(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_CARD'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_Card_UUID'),
                     primary_key=True,
                     nullable=False)

    profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    profile: Profile = db.relationship('Profile',
                                       primaryjoin=profile_id == Profile.uuid,
                                       backref=db.backref('cards',
                                                          order_by='Card.created_at.desc()'))
    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    user: user_module.User = db.relationship('User',
                                             primaryjoin=user_id == user_module.User.uuid,
                                             backref=db.backref('cards',
                                                                order_by='Card.created_at.desc()'))

    name = db.Column(db.String, unique=False, nullable=False)  # Card name shown in list or card detail page
    data = db.Column(db.String, unique=False, nullable=False)  # Card data (in json)

    subscribed_profile_relations: list['CardSubscription'] = None  # Backref of CardSubscription

    # if the card locked, then anyone cannot access, and this must not be shown on list.
    # This looks quite same as deleted, but...
    #   - card will be removed on all user's SQLITE DB
    #   - cannot be garbage collected
    #   - cannot recover by admin
    #   - only can be accessed by DB manager
    locked_at: datetime.datetime = db.Column(db.DateTime, nullable=True)
    why_locked = db.Column(db.String, nullable=True)
    locked_by_id = db.Column(db_module.PrimaryKeyType,
                             db.ForeignKey('TB_USER.uuid'),
                             nullable=True)
    locked_by = db.relationship(user_module.User, primaryjoin=locked_by_id == user_module.User.uuid)

    deleted_at: datetime.datetime = db.Column(db.DateTime, nullable=True)
    why_deleted = db.Column(db.String, nullable=True)
    deleted_by_id = db.Column(db_module.PrimaryKeyType,
                              db.ForeignKey('TB_USER.uuid'),
                              nullable=True)
    deleted_by = db.relationship(user_module.User, primaryjoin=deleted_by_id == user_module.User.uuid)

    private = db.Column(db.Boolean, default=False, nullable=False)
    modifiable = db.Column(db.Boolean, default=True, nullable=False)

    def to_dict(self, profile_id: int = None) -> dict:
        result = {
            'resource': 'card',

            'uuid': self.uuid,
            'profile_name': self.profile.name,  # TODO: MUST DO QUERY OPTIMIZATION!!!
            'card_name': self.name,
            'data': self.data,
            'preview_url': self.preview_url,

            'created_at': self.created_at,
            'modified': self.created_at != self.modified_at,
            'modified_at': self.modified_at,
        }

        if self.locked_at and profile_id == self.profile_id:
            result['locked'] = {
                'locked_at': self.locked_at.replace(tzinfo=utils.UTC),
                'locked_by': self.locked_by_id,
                'why_locked': self.why_locked
            }

        if self.deleted_at:
            result['deleted'] = {
                'deleted_at': self.deleted_at.replace(tzinfo=utils.UTC),
                'deleted_by': self.deleted_by_id,
                'why_deleted': self.why_deleted
            }
        return result


class CardSubscription(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_CARD_SUBSCRIPTION'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_CardSubscription_UUID'),
                     primary_key=True,
                     nullable=False)

    card_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_CARD.uuid'), nullable=False)
    card: Card = db.relationship('Card',
                                 primaryjoin=card_id == Card.uuid,
                                 backref=db.backref('subscribed_profile_relations',
                                                    order_by='CardSubscription.created_at.desc()'))

    profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    profile: Profile = db.relationship('Profile',
                                       primaryjoin=profile_id == Profile.uuid,
                                       backref=db.backref('card_subscribing',
                                                          order_by='CardSubscription.created_at.desc()'))
    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    user: user_module.User = db.relationship('User',
                                             primaryjoin=user_id == user_module.User.uuid,
                                             backref=db.backref('card_subscriptions',
                                                                order_by='Card.created_at.desc()'))

    profile_follow_rel_id = db.Column(db_module.PrimaryKeyType,
                                      db.ForeignKey('TB_PROFILE_FOLLOW.uuid'),
                                      nullable=False)
    profile_follow_rel: ProfileFollow = db.relationship(
                                    'ProfileFollow',
                                    primaryjoin=profile_follow_rel_id == ProfileFollow.uuid,
                                    backref=db.backref('subscripted_cards',  # on Profile class
                                                       order_by='CardSubscription.created_at.desc()'))
