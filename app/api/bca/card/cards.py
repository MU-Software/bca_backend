import flask
import flask.views
import json

import app.common.utils as utils
import app.api.helper_class as api_class
import app.api.common.file_manage as route_filemgr
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module
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
        description: Create card. Request need to include image file.
        responses:
            - resource_created
            - resource_not_found
            - resource_forbidden
            - body_empty
            - body_bad_semantics
            - server_error
        '''
        requested_profile_id = utils.safe_int(req_header['X-Profile-Id'])
        if str(requested_profile_id) not in access_token.role:
            return ResourceResponseCase.resource_forbidden.create_response()

        file_upload_enabled: bool = flask.current_app.config.get('FILE_MANAGEMENT_ROUTE_ENABLE', False)
        if not file_upload_enabled:
            return CommonResponseCase.http_forbidden.create_response(
                message='File upload is not enabled',
                data={'reason': 'File upload is not enabled'}, )

        target_profile = db.session.query(profile_module.Profile)\
            .filter(profile_module.Profile.locked_at.is_(None))\
            .filter(profile_module.Profile.deleted_at.is_(None))\
            .filter(profile_module.Profile.user_id == access_token.user)\
            .filter(profile_module.Profile.uuid == requested_profile_id)\
            .first()
        if not target_profile:
            return ResourceResponseCase.resource_not_found.create_response()

        # We'll handle upload first to make sure whether upload process success.
        # This calls internal REST API
        up_result: api_class.ResponseType = route_filemgr.FileManagementRoute().post()
        up_res_body, up_res_code, up_res_header = up_result
        if up_res_code != 201:  # Upload failed
            return up_result
        up_res_body = json.loads(up_res_body.data)

        new_card = profile_module.Card()
        new_card.user_id = target_profile.user_id
        new_card.profile_id = target_profile.uuid
        new_card.name = req_body['name']
        new_card.data = req_body['data']
        new_card.preview_url = up_res_body['file']['url']
        new_card.private = req_body.get('private', True)

        db.session.add(new_card)

        # Apply changeset on user db
        with sqs_action.UserDBJournalCreator(db):
            db.session.commit()

        return ResourceResponseCase.resource_created.create_response(
            header=(('ETag', new_card.commit_id, ), ),
            data={'card': new_card.to_dict(), })
