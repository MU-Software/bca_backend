import datetime
import flask
import flask.views
import typing

import app.api.helper_class as api_class
import app.common.utils as utils
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.profile as profile_module
import app.bca.sqs_action as sqs_action

from app.api.response_case import CommonResponseCase
from app.api.profiles.profile_response_case import ProfileResponseCase


class ProfileManagementRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={},
        optional_fields={'X-Csrf-Token': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: False, })
    def get(self,
            profile_id: int,
            req_header: dict,
            access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Get profile data of given UUID
        responses:
            - profile_found
            - profile_not_found
            - profile_forbidden
            - server_error
        '''
        try:
            target_profile: profile_module.Profile = profile_module.Profile.query\
                .filter(profile_module.Profile.locked_at != None)\
                .filter(profile_module.Profile.uuid == int(profile_id))\
                .first()  # noqa
            if not target_profile:
                return ProfileResponseCase.profile_not_found.create_response()

            if target_profile.private or target_profile.deleted_at is not None:
                # Check if profile is user's or user already subscribed this profile's card,
                # this will check only if access token is given, if not, then this will be failed.
                if not access_token:
                    return ProfileResponseCase.profile_forbidden.create_response()

                if access_token.role not in ('admin', ) and target_profile.user_id != access_token.user:
                    # Find all target profile's card, and find any relations of requested user and those cards
                    target_profile_cards_subquery = profile_module.Card.query\
                        .filter(profile_module.Card.profile_id == target_profile.uuid)\
                        .filter(profile_module.Card.locked_at != None)\
                        .subquery()  # noqa
                    profile_subscription = profile_module.CardSubscribed.query\
                        .filter(profile_module.CardSubscribed.card_id.in_(target_profile_cards_subquery))\
                        .filter(profile_module.CardSubscribed.profile_id.in_(access_token.profile_id))\
                        .scalar()
                    if not profile_subscription:
                        return ProfileResponseCase.profile_forbidden.create_response()

            return ProfileResponseCase.profile_found.create_response(
                header=(('ETag', target_profile.commit_id), ),
                data={'profile': target_profile.to_dict(), })
        except Exception:
            return CommonResponseCase.server_error.create_response()

    # # Modify profile
    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'If-Match': {'type': 'string', },
        },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        required_fields={},
        optional_fields={
            'email': {'type': 'string', },
            'phone': {'type': 'string', },
            'sns': {'type': 'string', },
            'description': {'type': 'string', },
            'data': {'type': 'string', },
            'private': {'type': 'boolean', }, })
    def patch(self,
              profile_id: int,
              req_header: dict,
              req_body: dict,
              access_token: jwt_module.AccessToken):
        '''
        description: Modify user's {profile_id} profile
        responses:
            - profile_modified
            - profile_not_found
            - profile_forbidden
            - profile_prediction_failed
            - header_invalid
            - header_required_omitted
            - server_error
        '''
        try:
            target_profile: profile_module.Profile = profile_module.Profile.query\
                .filter(profile_module.Profile.locked_at == None)\
                .filter(profile_module.Profile.deleted_at == None).first()  # noqa
            if not target_profile:
                return ProfileResponseCase.profile_not_found.create_response()
            if target_profile.user_id != access_token.user:
                # Check requested user is the owner of the profile
                return ProfileResponseCase.profile_forbidden.create_response()

            # Check Etag
            if req_header['If-Match'] != target_profile.commit_id:
                return ProfileResponseCase.profile_prediction_failed.create_response()

            # Modify this profile
            editable_columns = ('email', 'phone', 'sns', 'description', 'data', 'private')
            if not [col for col in editable_columns if col in req_body]:
                return CommonResponseCase.body_empty.create_response()

            for column in editable_columns:
                if column in req_body:
                    setattr(target_profile, column, req_body[column])

            user_db_changelog = sqs_action.create_changelog_from_session(db_module.db)
            db_module.db.session.commit()

            # Now, find the users that needs to be applied changelog on user db
            try:
                # Need to find all users that follows this profile
                profile_cards_subquery = db_module.db.session.query(profile_module.Card.uuid)\
                    .filter(profile_module.Card.profile_id == profile_id)\
                    .filter(profile_module.Card.locked_at != None)  # noqa
                profiles_that_subscribes_cards = db_module.db.session.query(profile_module.CardSubscribed.profile_id)\
                    .filter(profile_module.CardSubscribed.card_id.in_(profile_cards_subquery))
                users_id_of_profiles = db_module.db.session.query(profile_module.Profile.user_id)\
                    .filter(profile_module.Profile.uuid.in_(profiles_that_subscribes_cards))\
                    .filter(profile_module.Profile.locked_at != None)\
                    .distinct(profile_module.Profile.user_id).all()  # noqa

                for user_id in users_id_of_profiles:
                    sqs_action.UserDBModifyTaskMessage(user_id, user_db_changelog).add_to_queue()

            except Exception as err:
                print(utils.get_traceback_msg(err))

            return ProfileResponseCase.profile_deleted.create_response()
        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'If-Match': {'type': 'string', },
        },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self,
               profile_id: int,
               req_header: dict,
               access_token: jwt_module.AccessToken):
        '''
        description: Delete user's {profile_id} profile
        responses:
            - profile_deleted
            - profile_not_found
            - profile_forbidden
            - profile_prediction_failed
            - header_invalid
            - header_required_omitted
            - server_error
        '''
        try:
            target_profile: profile_module.Profile = profile_module.Profile.query\
                .filter(profile_module.Profile.locked_at == None)\
                .filter(profile_module.Profile.deleted_at == None).first()  # noqa
            if not target_profile:
                return ProfileResponseCase.profile_not_found.create_response()
            if target_profile.user_id != access_token.user and access_token.role not in ('admin', ):
                # Check requested user is admin or the owner of the profile
                return ProfileResponseCase.profile_forbidden.create_response()

            # Check Etag
            if req_header['If-Match'] != target_profile.commit_id:
                return ProfileResponseCase.profile_prediction_failed.create_response()

            # Delete this profile
            target_profile.deleted_at = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)
            target_profile.deleted_by_id = access_token.user
            target_profile.why_deleted = 'SELF_DELETED'

            user_db_changelog = sqs_action.create_changelog_from_session(db_module.db)
            db_module.db.session.commit()

            # Find the users that needs to be applied changelog on user db
            try:
                # Need to find all users that follows this profile
                profile_cards_subquery = db_module.db.session.query(profile_module.Card.uuid)\
                    .filter(profile_module.Card.profile_id == profile_id)\
                    .filter(profile_module.Card.locked_at != None)  # noqa
                profiles_that_subscribes_cards = db_module.db.session.query(profile_module.CardSubscribed.profile_id)\
                    .filter(profile_module.CardSubscribed.card_id.in_(profile_cards_subquery))
                users_id_of_profiles = db_module.db.session.query(profile_module.Profile.user_id)\
                    .filter(profile_module.Profile.uuid.in_(profiles_that_subscribes_cards))\
                    .filter(profile_module.Profile.locked_at != None)\
                    .distinct(profile_module.Profile.user_id).all()  # noqa

                for user_id in users_id_of_profiles:
                    sqs_action.UserDBModifyTaskMessage(user_id, user_db_changelog).add_to_queue()

            except Exception as err:
                print(utils.get_traceback_msg(err))

            return ProfileResponseCase.profile_deleted.create_response()
        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()
