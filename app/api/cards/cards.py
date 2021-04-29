import datetime
import flask
import flask.views
import typing

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.card as card_module

from app.api.response_case import CommonResponseCase
from app.api.cards.response_case import CardResponseCase


class CardRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={},
        optional_fields={
            'X-Csrf-Token': {'type': 'string', },
        },
        auth={api_class.AuthType.Bearer: False, })
    def get(self,
            card_id: int,
            req_header: dict,
            access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Returns card data
        responses:
            - card_found
            - card_not_found
            - card_forbidden
            - db_error
            - server_error
        '''
        try:
            target_card: card_module.Card = card_module.Card.query\
                .filter(card_module.Card.locked_at != None)\
                .filter(card_module.Card.deleted_at != None)\
                .filter(card_module.Card.uuid == card_id).first()  # noqa
            if not target_card:
                return CardResponseCase.card_not_found.create_response()

            # if target_card.private == False, then response card data
            if target_card.private:
                # if card is private, then only admin and card creator, card receiver can see this.
                if not access_token or\
                   access_token.role not in ('admin', ) or\
                   access_token.user == target_card.user_id:
                    # if someone subscribed this private card, then show it.
                    if access_token and not card_module.CardSubscribed.query\
                            .filter(card_module.Card.card_id == card_id)\
                            .filter(card_module.Card.user_id == access_token.user)\
                            .scalar():
                        return CardResponseCase.card_forbidden.create_response()

            card_data = target_card.to_dict()
            return CardResponseCase.card_found.create_response(
                data=card_data,
                header=(
                    ('ETag', target_card.commit_id),
                    ('Last-Modified', target_card.modified_at),
                ))
        except Exception:
            return CommonResponseCase.db_error.create_response()

    def put(self):
        pass

    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
        },
        optional_fields={
            'If-Match': {'type': 'string', },
            'If-Unmodified-Since': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self,
               card_id: int,
               req_header: dict,
               access_token: jwt_module.AccessToken):
        '''
        description: Returns card data
        responses:
            - card_found
            - card_not_found
            - card_forbidden
            - db_error
            - server_error
        '''
        try:
            target_card: card_module.Card = card_module.Card.query\
                .filter(card_module.Card.locked_at != None)\
                .filter(card_module.Card.deleted_at != None)\
                .filter(card_module.Card.uuid == card_id).first()  # noqa
            if not target_card:
                return CardResponseCase.card_not_found.create_response()

            # Card must be created by requested user
            if target_card.user_id != access_token.user:
                return CardResponseCase.card_forbidden.create_response()

            target_card.deleted_at = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)
            target_card.deleted_by_id = access_token.user
            db_module.db.session.commit()

            # TODO: Create lambda function calls to remove other user's db file
            subscribed_users = target_card.subscribed_user_relations
            for target_working_user in subscribed_users:
                # DO SOMETHING!
                pass

            return CardResponseCase.card_deleted.create_response(data={'id': target_card.uuid})
        except Exception:
            return CommonResponseCase.server_error.create_response()
