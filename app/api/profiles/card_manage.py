import datetime
import flask
import flask.views
import typing

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.profile as profile_module
import app.bca.sqs_action as sqs_action

from app.api.response_case import CommonResponseCase
from app.api.profiles.card_response_case import CardResponseCase


class CardManagementRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={},
        optional_fields={'X-Csrf-Token': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: False, })
    def get(self,
            profile_id: int,
            card_id: int,
            req_header: dict,
            access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Returns target card data
        responses:
            - card_found
            - card_not_found
            - card_forbidden
            - server_error
        '''
        try:
            target_card: profile_module.Card = profile_module.Card.query\
                .filter(profile_module.Card.profile_id == profile_id)\
                .filter(profile_module.Card.locked_at == None)\
                .filter(profile_module.Card.uuid == card_id).first()  # noqa
            if not target_card:
                return CardResponseCase.card_not_found.create_response()

            # if target_card.private == False, then response card data
            if target_card.private or target_card.deleted_at is not None:
                # if card is private, then only admin and card creator, card subscriber can see this.
                if not access_token:
                    return CardResponseCase.card_forbidden.create_response()

                # Private or deleted cards can be seen only by card subscriber, profile owner and admin
                if access_token.role not in ('admin', ) and target_card.profile_id not in access_token.profile_id:
                    # if user subscribed this private card, then show it.
                    if not profile_module.CardSubscription.query\
                            .filter(profile_module.Card.card_id == card_id)\
                            .filter(profile_module.Card.profile_id.in_(access_token.profile_id))\
                            .scalar():
                        return CardResponseCase.card_forbidden.create_response()

            return CardResponseCase.card_found.create_response(
                header=(('ETag', target_card.commit_id), ),
                data={'card': target_card.to_dict()}, )
        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'If-Match': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        required_fields={},
        optional_fields={
            'data': {'type': 'string', },
            'private': {'type': 'boolean', }, })
    def patch(self,
              profile_id: int,
              card_id: int,
              req_header: dict,
              req_body: dict,
              access_token: jwt_module.AccessToken):
        '''
        description: Modify user's card_id card. Only card creator can do card modification.
        responses:
            - card_modified
            - card_not_found
            - card_forbidden
            - db_error
            - server_error
        '''
        try:
            target_card: profile_module.Card = profile_module.Card.query\
                .filter(profile_module.Card.profile_id == profile_id)\
                .filter(profile_module.Card.locked_at == None)\
                .filter(profile_module.Card.deleted_at == None)\
                .filter(profile_module.Card.uuid == card_id).first()  # noqa
            if not target_card:
                return CardResponseCase.card_not_found.create_response()

            # Card can be deleted only by created user or admin
            if target_card.profile_id not in access_token.profile_id:
                return CardResponseCase.card_forbidden.create_response()

            # E-tag of request must be matched
            if target_card.commit_id != req_header.get('If-Match', None):
                return CardResponseCase.card_prediction_failed.create_response()

            # Modify card data
            editable_columns = ('data', 'private')
            if not [col for col in editable_columns if col in req_body]:
                return CommonResponseCase.body_empty.create_response()

            for column in editable_columns:
                if column in req_body:
                    setattr(target_card, column, req_body[column])

            user_db_changelog = sqs_action.create_changelog_from_session(db_module.db)
            db_module.db.session.commit()

            # Now, find the users that needs to be applied changelog on user db
            try:
                profiles_that_subscribes_cards = db_module.db.session.query(profile_module.CardSubscription.profile_id)\
                    .filter(profile_module.CardSubscription.card_id == card_id)
                users_id_of_profiles = db_module.db.session.query(profile_module.Profile.user_id)\
                    .filter(profile_module.Profile.uuid.in_(profiles_that_subscribes_cards))\
                    .filter(profile_module.Profile.locked_at == None)\
                    .distinct(profile_module.Profile.user_id).all()  # noqa
                users_id_of_profiles = [user_id[0] for user_id in users_id_of_profiles]

                for user_id in users_id_of_profiles:
                    sqs_action.UserDBModifyTaskMessage(user_id, user_db_changelog).add_to_queue()

            except Exception as err:
                print(utils.get_traceback_msg(err))

            return CardResponseCase.card_modified.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'If-Match': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self,
               profile_id: int,
               card_id: int,
               req_header: dict,
               access_token: jwt_module.AccessToken):
        '''
        description: Delete user's card_id card. Only card creator and admin can do card deletion.
        responses:
            - card_deleted
            - card_not_found
            - card_forbidden
            - db_error
            - server_error
        '''
        try:
            target_card: profile_module.Card = profile_module.Card.query\
                .filter(profile_module.Card.profile_id == profile_id)\
                .filter(profile_module.Card.locked_at == None)\
                .filter(profile_module.Card.deleted_at == None)\
                .filter(profile_module.Card.uuid == card_id).first()  # noqa
            if not target_card:
                return CardResponseCase.card_not_found.create_response()

            # Card can be deleted only by created user or admin
            if access_token.role not in ('admin', ) and target_card.profile_id not in access_token.profile_id:
                return CardResponseCase.card_forbidden.create_response()

            # E-tag of request must be matched
            if target_card.commit_id != req_header.get('If-Match', None):
                return CardResponseCase.card_prediction_failed.create_response()

            target_card.deleted_at = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)
            target_card.deleted_by_id = access_token.user
            target_card.why_deleted = 'SELF_DELETED'

            user_db_changelog = sqs_action.create_changelog_from_session(db_module.db)
            db_module.db.session.commit()

            # Now, find the users that needs to be applied changelog on user db
            try:
                profiles_that_subscribes_cards = db_module.db.session.query(profile_module.CardSubscription.profile_id)\
                    .filter(profile_module.CardSubscription.card_id == card_id)
                users_id_of_profiles = db_module.db.session.query(profile_module.Profile.user_id)\
                    .filter(profile_module.Profile.uuid.in_(profiles_that_subscribes_cards))\
                    .filter(profile_module.Profile.locked_at == None)\
                    .distinct(profile_module.Profile.user_id).all()  # noqa
                users_id_of_profiles = [user_id[0] for user_id in users_id_of_profiles]

                for user_id in users_id_of_profiles:
                    sqs_action.UserDBModifyTaskMessage(user_id, user_db_changelog).add_to_queue()

            except Exception as err:
                print(utils.get_traceback_msg(err))

            return CardResponseCase.card_deleted.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()
