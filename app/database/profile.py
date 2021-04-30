import datetime
import sqlalchemy.orm as sqlorm

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
    email = db.Column(db.String, nullable=True)  # Email of Profile
    phone = db.Column(db.String, nullable=True)  # Phone of Profile
    sns = db.Column(db.String, nullable=True)  # SNS Account of profile (in json)
    description = db.Column(db.String, nullable=True)  # Profile description
    data = db.Column(db.String, nullable=True)  # Profile additional data (in json)

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

    guestbook: board_module.Board = None  # Placeholder for backref
    announcement: board_module.Board = None  # Placeholder for backref

    def to_dict(self):
        result = {
            'id': self.uuid,
            'name': self.uuid,
            'description': self.uuid,
            'phone': self.uuid,
            'email': self.uuid,
            'sns': self.uuid,
            'data': self.uuid,

            'is_private': self.private,

            'created_at': self.created_at,
            'modified': self.created_at != self.modified_at,
            'modified_at': self.modified_at,
        }

        return {'profile': result, }


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

    name = db.Column(db.String, unique=False, nullable=False)  # Card name shown in list or card detail page
    data = db.Column(db.String, unique=False, nullable=False)  # Card data (in json)
    preview_url = db.Column(db.String, unique=True, nullable=False)  # Card preview image URL

    subscribed_profile_relations: list['CardSubscribed'] = None  # Backref of CardSubscribed

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
            'id': self.uuid,
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


class CardSubscribed(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_CARD_SUBSCRIBED'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_CardSubscribed_UUID'),
                     primary_key=True,
                     nullable=False)

    card_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_CARD.uuid'), nullable=False)
    card: Card = db.relationship('Card',
                                 primaryjoin=card_id == Card.uuid,
                                 backref=db.backref('subscribed_profile_relations',
                                                    order_by='CardSubscribed.created_at.desc()'))

    profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    profile: Profile = db.relationship('Profile',
                                       primaryjoin=profile_id == Profile.uuid,
                                       backref=db.backref('cards',
                                                          order_by='CardSubscribed.created_at.desc()'))

    @classmethod
    def get_followings(cls: 'CardSubscribed', profile_id: int) -> list:
        # We excluded Profile.deleted_at == None,
        # because there's a case that
        #  1. Profile B subscribed a Card 1 of Profile A,
        #  2. And Profile A deleted profile.
        # In this case, Profile B can access to Card 1 after deleting profile A,
        # and Card 1 is accessible through profile A.
        # Yeah, we need to left Profile A on Profile B's following lists
        result = CardSubscribed.query\
            .join(Card, CardSubscribed.card)\
            .options(sqlorm.contains_eager(CardSubscribed.card))\
            .join(Profile, Card.profile_id)\
            .options(sqlorm.contains_eager(Card.profile_id))\
            .filter(Profile.locked_at == None)\
            .filter(CardSubscribed.profile_id == profile_id)\
            .group_by(Card.profile_id)\
            .all()  # noqa

        return result
