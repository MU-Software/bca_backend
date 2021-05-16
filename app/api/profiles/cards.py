import flask
import flask.views
import secrets
import string
import typing

import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.profile as profile_module

from app.api.response_case import CommonResponseCase
from app.api.profiles.profile_response_case import ProfileResponseCase
from app.api.profiles.card_response_case import CardResponseCase


class CardMainRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={},
        optional_fields={'X-Csrf-Token': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: False, })
    def get(self,
            profile_id: int,
            req_header: dict,
            access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Returns all of profile_id's cards. Private cards can be seen only by profile owner or admin.
        responses:
            - multiple_cards_found
            - card_not_found
            - server_error
        '''
        try:
            target_cards: list[profile_module.Card] = profile_module.Card.query\
                .filter(profile_module.Card.locked_at != None)\
                .filter(profile_module.Card.deleted_at != None)\
                .filter(profile_module.Card.profile_id == profile_id)\
                .all()  # noqa
            if not target_cards:
                return CardResponseCase.card_not_found.create_response(
                    message='This profile doesn\'t have any card')

            response_cards: list[profile_module.Card] = list()
            for card in target_cards:
                if card.private:
                    # We cannot check permission if request doesn't include access token
                    if not access_token:
                        continue

                    # Profile's private cards can be seen only by card subscriber, profile owner and admin
                    if access_token.role not in ('admin', ) and profile_id not in access_token.profile_id:
                        card_subscribed: profile_module.CardSubscribed = profile_module.CardSubscribed.query\
                            .filter(profile_module.CardSubscribed.card_id == card.uuid)\
                            .filter(profile_module.CardSubscribed.profile_id.in_(access_token.profile_id)).scalar()
                        if not card_subscribed:
                            continue
                response_cards.append(card.to_dict())

            return CardResponseCase.multiple_cards_found.create_response(
                data={'cards': [card.to_dict() for card in response_cards], })

        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Csrf-Token': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        required_fields={
            'name': {'type': 'string', },
            'data': {'type': 'string', }, },
        optional_fields={
            'private': {'type': 'boolean', }, })
    def post(self,
             profile_id: int,
             req_body: dict,
             req_header: dict,
             access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Creates card
        responses:
            - profile_not_found
            - card_created
            - server_error
        '''
        try:
            if profile_id not in access_token.profile_id:
                return CardResponseCase.card_forbidden.create_response()

            target_profile: profile_module.Profile = profile_module.Profile.query\
                .filter(profile_module.Profile.locked_at != None)\
                .filter(profile_module.Profile.deleted_at != None)\
                .filter(profile_module.Profile.user_id == access_token.user)\
                .filter(profile_module.Profile.uuid == profile_id)\
                .first()  # noqa
            if not target_profile:
                return ProfileResponseCase.profile_not_found.create_response()

            new_card = profile_module.Card()
            new_card.profile = target_profile
            new_card.name = req_body['name']
            new_card.data = req_body['data']
            new_card.private = req_body.get('private', None)

            # TODO: Set proper value here
            new_card.preview_url = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))

            db_module.db.session.add(new_card)
            db_module.db.session.commit()

            return CardResponseCase.card_created.create_response(
                header=(('ETag', new_card.commit_id), ),
                data={'card': new_card.to_dict(), })
        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()
