import flask
import flask.views

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module

# import app.plugin.bca.sqs_action.action_definition as sqs_action_def
import app.plugin.bca.sqs_action as sqs_action

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db


class CardMainRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        optional_fields={'X-Profile-Id': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: False, })
    def get(self, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Returns my cards.
        responses:
            - multiple_resources_found
            - resource_not_found
            - resource_forbidden
            - server_error
        '''
        try:
            target_cards = db.session.query(profile_module.Card)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .filter(profile_module.Card.deleted_at.is_(None))\
                .filter(profile_module.Card.user_id == access_token.user)

            if 'X-Profile-Id' in req_header:
                requested_profile_id = utils.safe_int(req_header.get('X-Profile-Id', 0))
                if str(requested_profile_id) not in access_token.role:
                    return ResourceResponseCase.resource_forbidden.create_response(
                        message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

                target_cards = target_cards.filter(profile_module.Card.profile_id == requested_profile_id)

            target_cards = target_cards.all()
            if not target_cards:
                response_message = '해당 프로필엔 보유하신 명함이 없습니다.'\
                                   if 'X-Profile-Id' in req_header else '보유하신 명함이 없습니다.'
                return ResourceResponseCase.resource_not_found.create_response(message=response_message)

            return ResourceResponseCase.multiple_resources_found.create_response(
                data={'cards': [card.to_dict() for card in target_cards], })
        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer', }, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        required_fields={
            'name': {'type': 'string', },
            'data': {'type': 'string', }, },
        optional_fields={
            'private': {'type': 'boolean', }, })
    def post(self, req_body: dict, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Create card
        responses:
            - resource_created
            - resource_not_found
            - resource_forbidden
            - server_error
        '''
        try:
            requested_profile_id = utils.safe_int(req_header['X-Profile-Id'])
            if str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response()

            target_profile = db.session.query(profile_module.Profile)\
                .filter(profile_module.Profile.locked_at.is_(None))\
                .filter(profile_module.Profile.deleted_at.is_(None))\
                .filter(profile_module.Profile.user_id == access_token.user)\
                .filter(profile_module.Profile.uuid == requested_profile_id)\
                .first()
            if not target_profile:
                return ResourceResponseCase.resource_not_found.create_response()

            new_card = profile_module.Card()
            new_card.user_id = target_profile.user_id
            new_card.profile_id = target_profile.uuid
            new_card.name = req_body['name']
            new_card.data = req_body['data']
            new_card.private = req_body.get('private', True)

            db.session.add(new_card)

            # Apply changeset on user db
            with sqs_action.UserDBJournalCreator(db):
                db.session.commit()

            # # Apply new card data to user db
            # # This must be done after commit to get commit_id and modified_at columns' data
            # sqs_action_def.card_created(new_card)

            return ResourceResponseCase.resource_created.create_response(
                header=(('ETag', new_card.commit_id, ), ),
                data={'card': new_card.to_dict(), })
        except Exception:
            return CommonResponseCase.server_error.create_response()
