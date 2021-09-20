import base64
import flask
import flask.views

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database.jwt as jwt_module
import app.plugin.bca.s3_action as s3_action

from app.api.response_case import CommonResponseCase
from app.api.bca.sync.sync_response_case import SyncResponseCase


class SyncRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(auth={api_class.AuthType.Bearer: True, })
    def head(self, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Send DB hash
        responses:
            - sync_ok
            - server_error
        '''
        try:
            return SyncResponseCase.sync_ok.create_response(
                header=(('ETag', s3_action.get_user_db_md5(access_token.user)), ))
        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        optional_fields={'If-Match': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    def get(self, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Send DB hash
        responses:
            - sync_ok
            - sync_latest
            - server_error
        '''
        try:
            md5_placeholder = 'THISSTRINGCANNOTBETHEMD5`~!@#$%^&*()-_=+[{]};:\'"\\|,<.>/?'
            client_md5 = req_header.get('If-Match', md5_placeholder)
            if s3_action.check_user_db_md5(access_token.user, client_md5):
                return SyncResponseCase.sync_latest.create_response(
                    header=(('ETag', client_md5), ),
                )

            user_db_file_obj = s3_action.get_user_db(access_token.user)
            user_db_file_obj.seek(0)

            file_md5 = utils.fileobj_md5(user_db_file_obj)
            file_b64 = base64.b64encode(user_db_file_obj.read()).decode()
            user_db_file_obj.close()

            return SyncResponseCase.sync_ok.create_response(
                header=(('ETag', file_md5), ),
                data={'db': file_b64})

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(auth={api_class.AuthType.Bearer: True, })
    def delete(self, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Recreate User DB file
        responses:
            - sync_ok
            - sync_latest
            - server_error
        '''
        try:
            user_db_file_obj = s3_action.create_user_db(access_token.user, True, True)
            if not user_db_file_obj:
                raise Exception
            user_db_file_obj.seek(0)

            file_md5 = utils.fileobj_md5(user_db_file_obj)
            file_b64 = base64.b64encode(user_db_file_obj.read()).decode()
            user_db_file_obj.close()

            return SyncResponseCase.sync_ok.create_response(
                header=(('ETag', file_md5), ),
                data={'db': file_b64})

        except Exception:
            return CommonResponseCase.server_error.create_response()


resource_route = {
    '/sync/': SyncRoute,
}
