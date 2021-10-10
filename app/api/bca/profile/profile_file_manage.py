import base64
import enum
import flask
import flask.views
import pathlib as pt
import secrets
import time
import werkzeug.utils

import app.common.utils as utils
import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}


def allowed_file(filename: str):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


class BCaFileType(utils.EnumAutoName):
    PROFILE = enum.auto()
    CARD = enum.auto()


class ProfileFileRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(auth={api_class.AuthType.Bearer: True, }, )
    def get(self, profile_id: int, filename: str, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Returns target file.
            This returns binary file if request requested Content-Type as `not application/json`
        responses:
            - resource_found
            - resource_not_found
            - server_error
        '''
        try:
            filepath = pt.Path.cwd() / 'user_content' / str(profile_id) / 'uploads'
            filepath /= werkzeug.utils.secure_filename(filename)
            if not filepath.exists():
                return ResourceResponseCase.resource_not_found.create_response()

            request_content_type: str = flask.request.accept_mimetypes
            if 'application/json' in request_content_type:
                return ResourceResponseCase.resource_created.create_response(
                    data={'file': {
                        'resource': 'file',
                        'size': filepath.stat().st_size,
                        'data': base64.urlsafe_b64encode(filepath.read_bytes()).decode(), }, }, )
            else:
                return flask.send_file(filepath)

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer'}, },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestQuery(optional_fields={'filetype': {'type': 'string', }, }, )
    def post(self, profile_id: int, filename: str, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Upload new file.
        responses:
            - resource_modified
            - resource_not_found
            - server_error
        '''
        try:
            requested_profile_id = utils.safe_int(req_header.get('X-Profile-Id', 0))
            if 'X-Profile-Id' in req_header and str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

            api_ver = flask.current_app.config.get('RESTAPI_VERSION')

            # check if the post request has the file part
            if 'file' not in flask.request.files:
                return CommonResponseCase.body_empty.create_response()
            file = flask.request.files['file']
            # If the user does not select a file, the browser submits an
            # empty file without a filename.
            if file.filename == '':
                return CommonResponseCase.body_empty.create_response()

            filename = werkzeug.utils.secure_filename(file.filename)
            if file and allowed_file(filename):
                filepath = pt.Path.cwd() / 'user_content' / str(profile_id) / 'uploads'
                filename = '.'.join(filename.split('.')[:-1])
                filename += '-' + str(int(time.time())) + '-' + secrets.token_urlsafe(6)
                fileext = filename.split('.')[-1].lower()
                file.save(filepath / f'{filename}.{fileext}')

            return ResourceResponseCase.resource_created.create_response(
                data={'file': {
                    'resource': 'file',
                    'size': file.content_length,
                    'url': f'/api/{api_ver}/profiles/{profile_id}/uploads/{filename}', }, }, )

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(
        required_fields={'X-Profile-Id': {'type': 'integer'}, },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self, profile_id: int, filename: str, req_header: dict, access_token: jwt_module.AccessToken):
        '''
        description: Delete file.
        responses:
            - resource_deleted
            - resource_not_found
            - server_error
        '''
        try:
            requested_profile_id = utils.safe_int(req_header.get('X-Profile-Id', 0))
            if 'X-Profile-Id' in req_header and str(requested_profile_id) not in access_token.role:
                return ResourceResponseCase.resource_forbidden.create_response(
                    message='접속하고 계신 프로필은 본인의 프로필이 아닙니다.')

            filepath = pt.Path.cwd() / 'user_content' / str(profile_id) / 'uploads'
            filepath /= werkzeug.utils.secure_filename(filename)
            if not filepath.exists():
                return ResourceResponseCase.resource_not_found.create_response()

            filepath.unlink(True)

            return ResourceResponseCase.resource_deleted.create_response()

        except Exception:
            return CommonResponseCase.server_error.create_response()
