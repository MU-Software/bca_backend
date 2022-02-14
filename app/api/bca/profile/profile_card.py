import flask
import flask.views
import typing

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db


class ProfileCardRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        optional_fields={'X-Profile-Id': {'type': 'integer'}, },
        auth={api_class.AuthType.Bearer: False, })
    def get(self, profile_id: int, req_header: dict, access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Returns all profile_id cards.
            Private cards can be seen only by profile owner, card subscriber or admin.
        responses:
            - multiple_resources_found
            - resource_not_found
            - server_error
        '''
        try:
            target_cards = db.session.query(profile_module.Card)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .filter(profile_module.Card.profile_id == profile_id)\
                .all()
            if not target_cards:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='해당 프로필은 명함이 없습니다.')

            target_card_subscription_cache: list[profile_module.CardSubscription] = []
            if access_token and ('admin' not in access_token.role) and (str(profile_id) not in access_token.role):
                # Requested user is not a admin, and requested user is not a owner of target profile.
                # So we're going to query all the cards on the target profile
                # that requested profiles are subscribing to, rather than querying each cards seperately.
                if 'X-Profile-Id' in req_header:
                    requested_profile_id = utils.safe_int(req_header['X-Profile-Id'])
                    if str(requested_profile_id) not in access_token.role:
                        return ResourceResponseCase.resource_forbidden.create_response()

                    # Check if requested user subscribed the card.
                    # If requested user subscribed this card, then requested user can see this card anyway.
                    target_card_subscription_cache = db.session.query(profile_module.CardSubscription.uuid)\
                        .filter(profile_module.CardSubscription.subscribed_profile_id == requested_profile_id)\
                        .filter(profile_module.CardSubscription.card_profile_id == profile_id)\
                        .all()

            response_cards: list[profile_module.Card] = list()
            for card in target_cards:
                # Admin can see all cards
                if 'admin' in access_token.role:
                    response_cards.append(card)
                    continue

                # if card is not private and card is not deleted, then just add to response
                elif not card.private and not card.deleted_at:
                    response_cards.append(card)
                    continue

                # OK, card is private or deleted, we need to check if requested user can see this card.
                # We cannot check permission if request doesn't include access token
                elif not access_token:
                    continue

                # Card creator can see all private cards, except deleted cards
                elif card.user_id == access_token.user and not card.deleted_at:
                    response_cards.append(card)
                    continue

                # Check if requested user subscribed the card using cache,
                # and if it's subscribed, then show it.
                if card.uuid in target_card_subscription_cache:
                    response_cards.append(card)
                    continue

            if not response_cards:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='This profile doesn\'t have any card')

            return ResourceResponseCase.multiple_resources_found.create_response(
                data={'cards': [card.to_dict() for card in response_cards], })

        except Exception:
            return CommonResponseCase.server_error.create_response()
