import flask
import flask.views

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module
import app.plugin.bca.sqs_action.action_definition as sqs_action_def

from app.api.response_case import CommonResponseCase, ResourceResponseCase
from app.api.bca.card.card_response_case import CardResponseCase

db = db_module.db


class CardSubsctiptionRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    def get(self, card_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Return is requested profile subscribes this card
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
                return ResourceResponseCase.resource_forbidden.create_response()

            target_card = db.session.query(profile_module.Card)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .filter(profile_module.Card.uuid == card_id)\
                .first()
            if not target_card:
                return ResourceResponseCase.resource_not_found.create_response()

            # Check if profile already subscribed the card
            target_card_subscription = db.session.query(profile_module.CardSubscription)\
                .filter(profile_module.CardSubscription.profile_id == requested_profile_id)\
                .filter(profile_module.CardSubscription.card_id == card_id)\
                .first()
            if target_card_subscription:
                # Card is already subscribed!
                return CardResponseCase.card_already_subscribed.create_response()

            # If target card is marked as private or deleted, then we need to hide this card's existance
            if target_card.deleted_at or target_card.private:
                return ResourceResponseCase.resource_not_found.create_response()

            return CardResponseCase.card_not_subscribing.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'X-Profile-Id': {'type': 'integer', }, },
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
                return ResourceResponseCase.resource_forbidden.create_response()

            target_card = db.session.query(profile_module.Card)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .filter(profile_module.Card.deleted_at.is_(None))\
                .filter(profile_module.Card.uuid == card_id)\
                .first()
            if not target_card:
                return ResourceResponseCase.resource_not_found.create_response()

            # Check if card owner is the requested user
            # if it's ture, then block this
            if target_card.profile_id in access_token.role:
                return ResourceResponseCase.resource_conflict.create_response(
                    data={'conflict_reason': ['User cannot subscribe the card that is created by user self', ]})

            # Check if profile already subscribed the card
            target_card_subscription = db.session.query(profile_module.CardSubscription)\
                .filter(profile_module.CardSubscription.profile_id == requested_profile_id)\
                .filter(profile_module.CardSubscription.card_id == card_id)\
                .first()
            if target_card_subscription:
                # Card is already subscribed!
                return CardResponseCase.card_already_subscribed.create_response()

            # Make subscription record between the profile and the card
            # TODO: Add private key support for subscribing private cards
            if target_card.private:
                return ResourceResponseCase.resource_forbidden.create_response()

            # Check if requested user follows card owner.
            # If not, then create follow relation
            profile_1_id, profile_2_id = requested_profile_id, target_card.profile_id
            if profile_1_id > profile_2_id:
                profile_1_id, profile_2_id = profile_2_id, profile_1_id

            profile_follow_rel = db.session.query(profile_module.ProfileFollow)\
                .filter(profile_module.ProfileFollow.profile_1_id == profile_1_id)\
                .filter(profile_module.ProfileFollow.profile_2_id == profile_2_id)\
                .first()
            if not profile_follow_rel:
                profile_follow_rel = profile_module.ProfileFollow()
                profile_follow_rel.profile_1_id = profile_1_id
                profile_follow_rel.profile_2_id = profile_2_id
                # If it's not working, then we need to query these. Too bad!
                profile_follow_rel.user_1_id = profile_follow_rel.profile_1.user_id
                profile_follow_rel.user_2_id = profile_follow_rel.profile_2.user_id

                # OK, we need to mark user as follow
                profile_follow_rel.mark_as_follow(requested_profile_id)
                db.session.add(profile_follow_rel)
                db.session.commit()  # We need to commit to get UUID
            else:
                # Check if requested profile is following target profile.
                is_profile_following = profile_follow_rel.get_relation_explain()[(
                    requested_profile_id,
                    target_card.profile_id)]

                if not is_profile_following:
                    # OK, we need to mark user as follow
                    profile_follow_rel.mark_as_follow(requested_profile_id)

            new_subscription = profile_module.CardSubscription()
            new_subscription.profile_id = requested_profile_id
            new_subscription.user_id = access_token.user
            new_subscription.card_id = target_card.uuid
            new_subscription.profile_follow_rel_id = profile_follow_rel.uuid

            db.session.add(new_subscription)
            db.session.commit()

            # This must be done after commit to get commit_id and modified_at columns' data
            sqs_action_def.card_subscribed(new_subscription, target_card)

            return CardResponseCase.card_subscribed.create_response()

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
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
                return ResourceResponseCase.resource_forbidden.create_response()

            target_profile = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .first()
            if not target_profile:
                return ResourceResponseCase.resource_not_found.create_response()

            # Check if profile subscribes the card
            target_card_subscription = db.session.query(profile_module.CardSubscription)\
                .filter(profile_module.CardSubscription.profile_id == requested_profile_id)\
                .filter(profile_module.CardSubscription.card_id == card_id)\
                .first()
            if not target_card_subscription:
                # Card is not subscribing the card!
                return CardResponseCase.card_not_subscribing.create_response()

            # Apply card unsubscription on user db
            sqs_action_def.card_unsubscribed(target_card_subscription)

            db.session.delete(target_card_subscription)
            db.session.commit()

            return CardResponseCase.card_unsubscribed.create_response()

        except Exception:
            return CommonResponseCase.server_error.create_response()
