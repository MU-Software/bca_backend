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
from app.api.profiles.profile_response_case import ProfileResponseCase


class CardSubsctiptionRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def put(self, profile_id: int, card_id: int, req_header: dict,
            access_token: jwt_module.AccessToken):
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

            # Check if card owner is the requested user
            # if it's ture, then block this
            if target_card.profile_id in access_token.profile_id:
                return CardResponseCase.card_forbidden.create_response(
                    message='User cannot subscribe the card that is created by user self')

            # Check if profile already subscribed the card
            target_card_subscription: profile_module.CardSubscription = profile_module.CardSubscription.query\
                .filter(profile_module.CardSubscription.profile_id == target_profile_id)\
                .filter(profile_module.CardSubscription.card_id == card_id)\
                .first()
            if target_card_subscription:
                # Card is already subscribed!
                return CardResponseCase.card_already_subscribed.create_response()

            # Make subscription record between the profile and the card
            # TODO: Add private key support for subscribing private cards
            if target_card.private:
                return CardResponseCase.card_forbidden.create_response()

            new_subscription = profile_module.CardSubscription()
            new_subscription.profile_id = target_profile_id
            new_subscription.card_id = target_card.uuid

            db_module.db.session.add(new_subscription)
            user_db_changelog = sqs_action.create_changelog_from_session(db_module.db)
            db_module.db.session.commit()

            tgt_lg = [changelog for changelog in user_db_changelog if changelog.tablename == 'TB_CARD_SUBSCRIPTION'][0]
            tgt_lg.uuid = new_subscription.uuid

            sqs_action.UserDBModifyTaskMessage(target_profile_id, user_db_changelog).add_to_queue()

            return CardResponseCase.card_subscribed.create_response()

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

            target_profile: profile_module.Profile = profile_module.Profile.query\
                .filter(profile_module.Profile.uuid == profile_id)\
                .filter(profile_module.Profile.locked_at == None)\
                .filter(profile_module.Profile.deleted_at == None)\
                .first()  # noqa
            if not target_profile:
                return ProfileResponseCase.profile_not_found.create_response()

            # Check if profile subscribes the card
            target_card_subscription: profile_module.CardSubscription = profile_module.CardSubscription.query\
                .filter(profile_module.CardSubscription.profile_id == target_profile_id)\
                .filter(profile_module.CardSubscription.card_id == card_id)\
                .scalar()
            if not target_card_subscription:
                # Card is not subscribing the card!
                return CardResponseCase.card_not_subscribing.create_response()

            db_module.db.session.delete(target_card_subscription)
            user_db_changelog = sqs_action.create_changelog_from_session(db_module.db)
            db_module.db.session.commit()

            sqs_action.UserDBModifyTaskMessage(target_profile.user_id, user_db_changelog).add_to_queue()

            return CardResponseCase.card_unsubscribed.create_response()

        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()
