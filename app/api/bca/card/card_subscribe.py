import flask
import flask.views

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module
import app.plugin.bca.user_db.sqs_action as sqs_action

from app.api.response_case import CommonResponseCase, ResourceResponseCase
from app.api.bca.card.cardsubscription_response_case import CardSubscriptionResponseCase

db = db_module.db


class CardSubsctiptionRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def get(self, card_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Returns requested profile is subscribing this card
        responses:
            - card_already_subscribed
            - card_not_subscribing
            - resource_not_found
            - resource_forbidden
            - server_error
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

            target_card = db.session.query(profile_module.Card)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .filter(profile_module.Card.uuid == card_id)\
                .first()
            if not target_card:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='해당 명함을 찾을 수 없습니다.',
                    data={'resource_name': ['card', ]})

            # Check if profile subscribed the card
            target_card_subscription = db.session.query(profile_module.CardSubscription)\
                .filter(profile_module.CardSubscription.subscribed_profile_id == requested_profile_id)\
                .filter(profile_module.CardSubscription.card_id == target_card.uuid)\
                .first()
            if not target_card_subscription:
                # If target card is marked as deleted, then we need to hide this card's existance
                if target_card.deleted_at:
                    return ResourceResponseCase.resource_not_found.create_response()

                return CardSubscriptionResponseCase.card_not_subscribing.create_response(
                    message='해당 명함은 구독 시에만 볼 수 있습니다.')

            # Requested profile is subscribing this card!
            return CardSubscriptionResponseCase.card_already_subscribed.create_response(
                message='현재 명함을 구독 중입니다.')

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def put(self, card_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Subscribe this card
        responses:
            - resource_not_found
            - resource_forbidden
            - card_subscribed
            - card_already_subscribed
            - server_error
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

            # TODO: Add private time based otp support for subscribing private cards
            target_card = db.session.query(profile_module.Card)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .filter(profile_module.Card.deleted_at.is_(None))\
                .filter(profile_module.Card.private.is_(False))\
                .filter(profile_module.Card.uuid == card_id)\
                .first()
            if not target_card:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='해당 명함을 찾을 수 없습니다.',
                    data={'resource_name': ['card', ]})

            # Block when card owner requested to subscribe their cards
            if target_card.user_id == access_token.user:
                return ResourceResponseCase.resource_conflict.create_response(
                    message='본인의 명함은 구독할 수 없습니다.',
                    data={'conflict_reason': ['본인의 명함은 구독할 수 없습니다.', ]})

            # Check if profile already subscribed the card
            target_card_subscription = db.session.query(profile_module.CardSubscription)\
                .filter(profile_module.CardSubscription.subscribed_profile_id == requested_profile_id)\
                .filter(profile_module.CardSubscription.card_id == card_id)\
                .first()
            if target_card_subscription:
                # Card is already subscribed!
                return CardSubscriptionResponseCase.card_already_subscribed.create_response(
                    message='이미 해당 명함을 구독하셨습니다.')

            # Find relationship between requested profile and target card's profile.
            # If it's not found, then create new relations.
            request_to_target_rel = db.session.query(profile_module.ProfileRelation)\
                .filter(profile_module.ProfileRelation.from_profile_id == requested_profile_id)\
                .filter(profile_module.ProfileRelation.to_profile_id == target_card.profile_id)\
                .first()
            target_to_request_rel = db.session.query(profile_module.ProfileRelation)\
                .filter(profile_module.ProfileRelation.from_profile_id == target_card.profile_id)\
                .filter(profile_module.ProfileRelation.to_profile_id == requested_profile_id)\
                .first()

            # If those two relations are all None,
            # then we can assumes that this is the first time they are getting relationship.
            # Let's make them both following each other!
            if not request_to_target_rel and not target_to_request_rel:
                request_to_target_rel = profile_module.ProfileRelation()
                request_to_target_rel.from_user_id = access_token.user
                request_to_target_rel.from_profile_id = requested_profile_id
                request_to_target_rel.to_user_id = target_card.user_id
                request_to_target_rel.to_profile_id = target_card.profile_id
                request_to_target_rel.status = profile_module.ProfileRelationStatus.FOLLOW

                target_to_request_rel = profile_module.ProfileRelation()
                target_to_request_rel.from_user_id = target_card.user_id
                target_to_request_rel.from_profile_id = target_card.profile_id
                target_to_request_rel.to_user_id = access_token.user
                target_to_request_rel.to_profile_id = requested_profile_id
                target_to_request_rel.status = profile_module.ProfileRelationStatus.FOLLOW

                db.session.add(request_to_target_rel)
                db.session.add(target_to_request_rel)

            # Finally, make subscription record between the profile and the card
            new_subscription = profile_module.CardSubscription()
            new_subscription.subscribed_user_id = access_token.user
            new_subscription.subscribed_profile_id = requested_profile_id
            new_subscription.card_user_id = target_card.user_id
            new_subscription.card_profile_id = target_card.profile_id
            new_subscription.card_id = target_card.uuid

            db.session.add(new_subscription)

            # Apply changeset on user db
            with sqs_action.UserDBJournalCreator(db):
                db.session.commit()

            return CardSubscriptionResponseCase.card_subscribed.create_response()

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self, card_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Unsubscribe this card
        responses:
            - resource_not_found
            - card_unsubscribed
            - card_not_subscribing
            - server_error
        '''
        try:
            requested_profile_id: int = utils.safe_int(req_header['X-Profile-Id'])
            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

            # Check if profile subscribes the card
            target_card_subscription = db.session.query(profile_module.CardSubscription)\
                .filter(profile_module.CardSubscription.subscribed_profile_id == requested_profile_id)\
                .filter(profile_module.CardSubscription.card_id == card_id)\
                .first()
            if not target_card_subscription:
                # Card is not subscribing the card!
                return CardSubscriptionResponseCase.card_not_subscribing.create_response()

            db.session.delete(target_card_subscription)

            # Apply changeset on user db
            with sqs_action.UserDBJournalCreator(db):
                db.session.commit()

            return CardSubscriptionResponseCase.card_unsubscribed.create_response()

        except Exception:
            return CommonResponseCase.server_error.create_response()
