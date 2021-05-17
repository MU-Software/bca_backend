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


class CardSubsctiptionRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def put(self, profile_id: int, card_id: int, req_header: dict,
            access_token: typing.Optional[jwt_module.AccessToken]):
        '''
        description: Subscribe this card
        responses:
            - card_not_found
            - card_forbidden
            - card_subscribed
            - card_already_subscribed
            - server_error
        '''
        try:
            target_card: profile_module.Card = profile_module.Card.query\
                .filter(profile_module.Card.locked_at == None)\
                .filter(profile_module.Card.deleted_at == None)\
                .filter(profile_module.Card.profile_id == profile_id)\
                .filter(profile_module.Card.uuid == card_id)\
                .first()  # noqa
            if not target_card:
                return CardResponseCase.card_not_found.create_response()

            target_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])

            if target_profile_id not in access_token.profile_id:
                return CardResponseCase.card_forbidden.create_response()

            # Check if profile already subscribed the card
            target_card_subscription: profile_module.CardSubscribed = profile_module.CardSubscribed.query\
                .filter(profile_module.CardSubscribed.profile_id == target_profile_id)\
                .filter(profile_module.CardSubscribed.card_id == card_id)\
                .scalar()
            if target_card_subscription:
                # Card is already subscribed!
                return CardResponseCase.card_already_subscribed.create_response()

            # Make subscription record between the profile and the card
            # TODO: Add private key support for subscribing private cards
            if target_card.private:
                return CardResponseCase.card_forbidden.create_response()

            new_subscription = profile_module.CardSubscribed()
            new_subscription.profile_id = target_profile_id
            new_subscription.card_id = target_card.uuid

            db_module.db.session.add(new_subscription)
            sqs_action.create_changelog_from_session(db_module.db)
            db_module.db.session.commit()

        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self, profile_id: int, card_id: int, req_header: dict,
               access_token: typing.Optional[jwt_module.AccessToken]):
        '''
        description: Subscribe this card
        responses:
            - card_not_found
            - card_unsubscribed
            - card_not_subscribing
            - server_error
        '''
        try:
            target_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])

            if target_profile_id not in access_token.profile_id:
                return CardResponseCase.card_forbidden.create_response()

            # Check if profile subscribes the card
            target_card_subscription: profile_module.CardSubscribed = profile_module.CardSubscribed.query\
                .filter(profile_module.CardSubscribed.profile_id == target_profile_id)\
                .filter(profile_module.CardSubscribed.card_id == card_id)\
                .scalar()
            if not target_card_subscription:
                # Card is not subscribing the card!
                return CardResponseCase.card_not_subscribing.create_response()

            db_module.db.session.delete(target_card_subscription)
            sqs_action.create_changelog_from_session(db_module.db)
            db_module.db.session.commit()

            return CardResponseCase.card_unsubscribed.create_response()

        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()
