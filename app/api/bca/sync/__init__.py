import flask
import flask.views

import app.api.helper_class as api_class
import app.database.jwt as jwt_module
import app.plugin.bca.user_db.file_io as bca_sync_file_io

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
                header=(('ETag', bca_sync_file_io.BCaSyncFile.get_hash(access_token.user)), ))
        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        optional_fields={'If-Match': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    def get(self, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Send DB file data as URL-safe base64
        responses:
            - sync_ok
            - sync_latest
            - server_error
        '''
        try:
            md5_placeholder = 'THISSTRINGCANNOTBETHEMD5`~!@#$%^&*()-_=+[{]};:\'"\\|,<.>/?'
            client_md5 = req_header.get('If-Match', md5_placeholder)

            if bca_sync_file_io.BCaSyncFile.check_hash(user_id=access_token.user, hash_str=client_md5):
                return SyncResponseCase.sync_latest.create_response(header=(('ETag', client_md5), ), )

            try:
                user_db_obj = bca_sync_file_io.BCaSyncFile.load(access_token.user)
            except FileNotFoundError:
                user_db_obj = bca_sync_file_io.BCaSyncFile.create(access_token.user, True, True)

            file_md5 = user_db_obj.get_hash()
            file_b64 = user_db_obj.as_b64urlsafe()
            return SyncResponseCase.sync_ok.create_response(header=(('ETag', file_md5), ), data={'db': file_b64})

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
            user_db_obj = bca_sync_file_io.BCaSyncFile.create(access_token.user, True, True)
            file_md5 = user_db_obj.get_hash()
            file_b64 = user_db_obj.as_b64urlsafe()
            return SyncResponseCase.sync_ok.create_response(
                header=(('ETag', file_md5), ),
                data={'db': file_b64})

        except Exception:
            return CommonResponseCase.server_error.create_response()


resource_route = {
    '/sync': SyncRoute,
}
