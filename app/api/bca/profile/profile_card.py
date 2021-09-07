import flask
import flask.views
import typing

import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db


class ProfileCardRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={},
        optional_fields={'X-Csrf-Token': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: False, })
    def get(self, profile_id: int, req_header: dict, access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Returns all of profile_id's cards. Private cards can be seen only by profile owner or admin.
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
                    message='This profile doesn\'t have any card')

            response_cards: list[profile_module.Card] = list()
            for card in target_cards:
                # We cannot check permission if request doesn't include access token
                if not access_token:
                    continue

                # Admin can see all cards
                elif 'admin' in access_token.role:
                    response_cards.append(card)
                    continue

                # Check if requested user subscribed the card
                target_card_subscription = db.session.query(profile_module.CardSubscription)\
                    .filter(profile_module.CardSubscription.user_id == access_token.user)\
                    .filter(profile_module.CardSubscription.card_id == card.uuid)\
                    .first()

                if card.deleted_at and target_card_subscription:
                    response_cards.append(card)
                    continue

                elif card.private and (card.user_id == access_token.user or target_card_subscription):
                    response_cards.append(card)
                    continue

            return ResourceResponseCase.multiple_resources_found.create_response(
                data={'cards': [card.to_dict() for card in response_cards], })

        except Exception:
            return CommonResponseCase.server_error.create_response()
