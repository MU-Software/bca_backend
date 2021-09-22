import datetime
import enum

import app.common.utils as utils
import app.database as db_module
import app.database.user as user_module

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
    data = db.Column(db.String, nullable=False)  # Profile data (in json)
    email = db.Column(db.String, nullable=True)  # Main email of Profile
    phone = db.Column(db.String, nullable=True)  # Main phone of Profile
    address = db.Column(db.String, nullable=True)  # Main address of Profile
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

    is_follow_list_public = db.Column(db.Boolean, default=False, nullable=False)
    can_annonymous_invite = db.Column(db.Boolean, default=False, nullable=False)

    relation_from: list['ProfileRelation'] = None  # Placeholder for backref
    relation_to: list['ProfileRelation'] = None  # Placeholder for backref

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


class ProfileRelationStatus(enum.Enum):
    FOLLOW = 1  # Shows in list, and Opponent can send chat to here
    HIDE = 2  # Don't show in list, but Opponent can send chat to here
    BLOCK = 3  # Don't show in list, and Opponent can't send chat to here
    # DELETE must delete this relation
    FOLLOW_REQUESTED = 4  # This must be treated as 'not followed'.


class ProfileRelation(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_PROFILE_RELATION'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_Profile_UUID'),
                     primary_key=True,
                     nullable=False)

    from_user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    from_user: user_module.User = db.relationship('User', primaryjoin=from_user_id == user_module.User.uuid)
    from_profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    from_profile: Profile = db.relationship('Profile',
                                            primaryjoin=from_profile_id == Profile.uuid,
                                            backref=db.backref('relation_from',
                                                               order_by='ProfileRelation.created_at.desc()'))

    to_user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    to_user: user_module.User = db.relationship('User', primaryjoin=to_user_id == user_module.User.uuid)
    to_profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    to_profile: Profile = db.relationship('Profile',
                                          primaryjoin=to_profile_id == Profile.uuid,
                                          backref=db.backref('relation_to',
                                                             order_by='ProfileRelation.created_at.desc()'))

    status = db.Column(db.Enum(ProfileRelationStatus), nullable=False, default=ProfileRelationStatus.FOLLOW)

    subscripted_cards: list['CardSubscription'] = None


class Card(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_CARD'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_Card_UUID'),
                     primary_key=True,
                     nullable=False)

    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    user: user_module.User = db.relationship('User',
                                             primaryjoin=user_id == user_module.User.uuid,
                                             backref=db.backref('cards',
                                                                order_by='Card.created_at.desc()'))
    profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    profile: Profile = db.relationship('Profile',
                                       primaryjoin=profile_id == Profile.uuid,
                                       backref=db.backref('cards',
                                                          order_by='Card.created_at.desc()'))

    name = db.Column(db.String, unique=False, nullable=False)  # Card name shown in list or card detail page
    data = db.Column(db.String, unique=False, nullable=False)  # Card data (in json)
    preview_url = db.Column(db.String, unique=False, nullable=False)  # Card preview image url

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
            'profile_name': self.profile.name,
            'card_name': self.name,
            'data': self.data,
            'preview_url': self.preview_url,

            'created_at': self.created_at,
            'modified': self.created_at != self.modified_at,
            'modified_at': self.modified_at,
        }

        if self.locked_at:
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

    card_user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    card_user: user_module.User = db.relationship('User', primaryjoin=card_user_id == user_module.User.uuid)
    card_profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    card_profile: Profile = db.relationship('Profile', primaryjoin=card_profile_id == Profile.uuid)
    card_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_CARD.uuid'), nullable=False)
    card: Card = db.relationship('Card',
                                 primaryjoin=card_id == Card.uuid,
                                 backref=db.backref('subscribed_profile_relations',
                                                    order_by='CardSubscription.created_at.desc()'))

    subscribed_user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    subscribed_user: user_module.User = db.relationship(
                                            'User',
                                            primaryjoin=subscribed_user_id == user_module.User.uuid,
                                            backref=db.backref('card_subscriptions',
                                                               order_by='Card.created_at.desc()'))
    subscribed_profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    subscribed_profile: Profile = db.relationship(
                                        'Profile',
                                        primaryjoin=subscribed_profile_id == Profile.uuid,
                                        backref=db.backref('card_subscribing',
                                                           order_by='CardSubscription.created_at.desc()'))

    # from_profile_rel_id = db.Column(db_module.PrimaryKeyType,
    #                                 db.ForeignKey('TB_PROFILE_RELATION.uuid'),
    #                                 nullable=False)
    # from_profile_rel: ProfileRelation = db.relationship(
    #                                 'ProfileRelation',
    #                                 primaryjoin=from_profile_rel_id == ProfileRelation.uuid)

    # to_profile_rel_id = db.Column(db_module.PrimaryKeyType,
    #                               db.ForeignKey('TB_PROFILE_RELATION.uuid'),
    #                               nullable=False)
    # to_profile_rel: ProfileRelation = db.relationship(
    #                                 'ProfileRelation',
    #                                 primaryjoin=from_profile_rel_id == ProfileRelation.uuid)
