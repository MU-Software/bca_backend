import datetime
import flask
import flask.views
import typing

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.bca.profile as profile_module
import app.plugin.bca.user_db.sqs_action as sqs_action

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db


class CardManagementRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(auth={api_class.AuthType.Bearer: False, })
    def get(self, card_id: int, req_header: dict, access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Returns target card data
        responses:
            - resource_found
            - resource_not_found
            - resource_forbidden
            - server_error
        '''
        try:
            target_card = db.session.query(profile_module.Card)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .filter(profile_module.Card.uuid == card_id).first()
            if not target_card:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='명함을 찾을 수 없습니다.')

            # if target_card.private == False, then response card data
            if target_card.private or target_card.deleted_at is not None:
                # if card is private, then only admin and card creator, card subscriber can see this.
                if not access_token:
                    return ResourceResponseCase.resource_forbidden.create_response(
                        message='명함을 보려면 로그인이 필요합니다.')

                elif 'admin' in access_token.role:
                    return ResourceResponseCase.resource_found.create_response(
                        header=(('ETag', target_card.commit_id, ), ),
                        data={'card': target_card.to_dict()}, )

                # Get subscriber records
                card_subscription_rel = db.session.query(profile_module.CardSubscription)\
                    .filter(profile_module.CardSubscription.uuid == card_id)\
                    .filter(profile_module.CardSubscription.user_id == access_token.user)\
                    .all()

                # Deleted cards can be seen only by card subscriber and admin
                if target_card.deleted_at is not None and card_subscription_rel:
                    return ResourceResponseCase.resource_found.create_response(
                        header=(('ETag', target_card.commit_id, ), ),
                        data={'card': target_card.to_dict()}, )

                # Private cards, on the other hands, can be seen by card subscriber, profile owner and admin
                elif target_card.private:
                    if target_card.user_id == access_token.user or card_subscription_rel:
                        return ResourceResponseCase.resource_found.create_response(
                            header=(('ETag', target_card.commit_id, ), ),
                            data={'card': target_card.to_dict()}, )

                return ResourceResponseCase.resource_forbidden.create_response(
                        message='명함을 볼 권한이 없습니다.')

            return ResourceResponseCase.resource_found.create_response(
                header=(('ETag', target_card.commit_id, ), ),
                data={'card': target_card.to_dict()}, )

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'If-Match': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        optional_fields={
            'data': {'type': 'string', },
            'private': {'type': 'boolean', }, })
    def patch(self, card_id: int, req_header: dict, req_body: dict, access_token: jwt_module.AccessToken):
        '''
        description: Modify user's card_id card. Only card creator can do card modification.
        responses:
            - resource_modified
            - resource_not_found
            - resource_forbidden
            - db_error
            - server_error
        '''
        try:
            target_card = db.session.query(profile_module.Card)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .filter(profile_module.Card.deleted_at.is_(None))\
                .filter(profile_module.Card.user_id == access_token.user)\
                .filter(profile_module.Card.uuid == card_id).first()
            if not target_card:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='명함을 찾을 수 없습니다.')

            # Card can be deleted only by created user or admin
            if target_card.profile_id not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='명함 수정은 명함 제작자만이 할 수 있습니다.')

            # E-tag of request must be matched
            if target_card.commit_id != req_header.get('If-Match', None):
                return ResourceResponseCase.resource_prediction_failed.create_response(
                    message='명함이 다른 기기에서 수정된 것 같습니다.\n동기화를 해 주세요.')

            # Modify card data
            editable_columns = ('data', 'private')
            filtered_data = {col: data for col, data in req_body.items() if col in editable_columns}
            if not filtered_data:
                return CommonResponseCase.body_empty.create_response()
            for column, data in filtered_data.items():
                setattr(target_card, column, data)

            # Apply changeset on user db
            with sqs_action.UserDBJournalCreator(db):
                db.session.commit()

            return ResourceResponseCase.resource_modified.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'If-Match': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self, card_id: int, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Delete user's card_id card. Only card creator and admin can do card deletion.
        responses:
            - resource_deleted
            - resource_not_found
            - resource_forbidden
            - db_error
            - server_error
        '''
        try:
            target_card = db.session.query(profile_module.Card)\
                .filter(profile_module.Card.locked_at.is_(None))\
                .filter(profile_module.Card.deleted_at.is_(None))\
                .filter(profile_module.Card.uuid == card_id).first()
            if not target_card:
                return ResourceResponseCase.resource_not_found.create_response(
                    message='명함을 찾을 수 없습니다.')

            # Card can be deleted only by created user or admin
            if 'admin' not in access_token.role and target_card.profile_id not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='명함 삭제는 관리자나 명함 제작자만이 할 수 있습니다.')

            # E-tag of request must be matched
            if target_card.commit_id != req_header.get('If-Match', None):
                return ResourceResponseCase.resource_prediction_failed.create_response(
                    message='명함이 다른 기기에서 수정된 것 같습니다.\n동기화를 해 주세요.')

            target_card.deleted_at = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)
            target_card.deleted_by_id = access_token.user
            target_card.why_deleted = 'DELETE_REQUESTED'

            # Apply changeset on user db
            with sqs_action.UserDBJournalCreator(db):
                db.session.commit()

            return ResourceResponseCase.resource_deleted.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()
