import typing

import app.database as db_module
import app.database.user as user_module
import app.database.bca.profile as profile_module

db = db_module.db


class ThirdPartyService(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_THIRDPARTY_SERVICE'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_ThirdPartyService_UUID'),
                     primary_key=True,
                     nullable=False)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=True)
    private = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    locked_at = db.Column(db.DateTime, nullable=True)

    created_by_user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    created_by_user: user_module.User = db.relationship(
                                            'User',
                                            primaryjoin=created_by_user_id == user_module.User.uuid)
    created_by_profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    created_by_profile: profile_module.Profile = db.relationship(
                                            'Profile',
                                            primaryjoin=created_by_profile_id == profile_module.Profile.uuid)

    participants: list['ThirdPartyParticipant'] = None  # Placeholder for backref

    def find_participant(self, profile_id: int) -> typing.Optional['ThirdPartyParticipant']:
        return db.session.query(ThirdPartyParticipant)\
            .filter(ThirdPartyParticipant.service_id == self.uuid)\
            .filter(ThirdPartyParticipant.profile_id == profile_id)\
            .first()

    def to_dict(self):
        return {
            'resource': 'thirdparty_service',
            'uuid': self.uuid,
            'name': self.name,
            'private': self.private,
            'description': self.description,

            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'modified': self.created_at != self.modified_at,
            'commit_id': self.commit_id,
        }


class ThirdPartyParticipant(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_THIRDPARTY_PARTICIPANT'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_ThirdPartyParticipant_UUID'),
                     primary_key=True,
                     nullable=False)

    service_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_THIRDPARTY_SERVICE.uuid'), nullable=False)
    service: ThirdPartyService = db.relationship(
                            'ThirdPartyService',
                            primaryjoin=service_id == ThirdPartyService.uuid,
                            backref=db.backref('participants'))

    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    user: user_module.User = db.relationship('User', primaryjoin=user_id == user_module.User.uuid)
    profile_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_PROFILE.uuid'), nullable=False)
    profile: profile_module.Profile = db.relationship('Profile', primaryjoin=profile_id == profile_module.Profile.uuid)

    def to_dict(self):
        return {
            'resource': 'thirdparty_participant',
            'uuid': self.uuid,
            'service_id': self.service_id,
            'service': self.service.to_dict(),
            'profile_id': self.profile_id,
            'profile': self.profile.to_dict(),

            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'modified': self.created_at != self.modified_at,
            'commit_id': self.commit_id,
        }
