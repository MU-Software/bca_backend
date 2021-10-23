import base64
import flask
import flask.views
import pathlib as pt
import secrets
import time
import typing
import werkzeug.utils

import app.api.helper_class as api_class
import app.database as db_module
import app.database.jwt as jwt_module

from app.api.response_case import CommonResponseCase, ResourceResponseCase

db = db_module.db
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}


def allowed_file(filename: str):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


class FileRoute(flask.views.MethodView, api_class.MethodViewMixin):
    def get(self, filename: typing.Optional[str] = None):
        '''
        description: Returns target file.
            This returns binary file if request requested Content-Type as `not application/json`
        responses:
            - resource_found
            - resource_not_found
            - http_forbidden
            - server_error
        '''
        try:
            if not filename:
                return CommonResponseCase.http_forbidden.create_response()

            filepath = pt.Path.cwd() / 'user_content' / 'uploads'
            filepath /= werkzeug.utils.secure_filename(filename)
            if not filepath.exists():
                return ResourceResponseCase.resource_not_found.create_response()

            request_content_type: str = flask.request.accept_mimetypes
            if 'image/*' in request_content_type:
                return flask.send_file(filepath)
            elif 'application/json' in request_content_type:
                return ResourceResponseCase.resource_created.create_response(
                    data={'file': {
                        'resource': 'file',
                        'size': filepath.stat().st_size,
                        'data': base64.urlsafe_b64encode(filepath.read_bytes()).decode(), }, }, )
            else:
                return flask.send_file(filepath)

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(auth={api_class.AuthType.Bearer: True, })
    def post(self, req_header: dict, access_token: jwt_module.AccessToken, filename: typing.Optional[str] = None):
        '''
        description: Upload new file.
        responses:
            - resource_modified
            - resource_not_found
            - http_forbidden
            - server_error
        '''
        try:
            if filename:
                return CommonResponseCase.http_forbidden.create_response()

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
                filepath = pt.Path.cwd() / 'user_content' / 'uploads'
                result_filename = '.'.join(filename.split('.')[:-1])
                result_filename += '-' + str(access_token.user)
                result_filename += '-' + str(int(time.time()))
                result_filename += '-' + secrets.token_urlsafe(6)
                fileext = filename.split('.')[-1].lower()
                file.save(filepath / f'{result_filename}.{fileext}')

                return ResourceResponseCase.resource_created.create_response(
                    data={'file': {
                        'resource': 'file',
                        'size': file.content_length,
                        'url': f'/uploads/{result_filename}.{fileext}', }, }, )

            return ResourceResponseCase.resource_forbidden.create_response()

        except Exception:
            return CommonResponseCase.server_error.create_response()

    @api_class.RequestHeader(auth={api_class.AuthType.Bearer: True, })
    def delete(self, req_header: dict, access_token: jwt_module.AccessToken, filename: typing.Optional[str] = None):
        '''
        description: Delete file.
        responses:
            - resource_deleted
            - resource_not_found
            - resource_forbidden
            - http_not_found
            - server_error
        '''
        try:
            if not filename:
                return CommonResponseCase.http_not_found.create_response()

            filepath = pt.Path.cwd() / 'user_content' / 'uploads'
            filepath /= werkzeug.utils.secure_filename(filename)
            if not filepath.exists():
                return ResourceResponseCase.resource_not_found.create_response()
            if str(access_token.user) not in filepath:
                return ResourceResponseCase.resource_forbidden.create_response()

            filepath.unlink(True)

            return ResourceResponseCase.resource_deleted.create_response()

        except Exception:
            return CommonResponseCase.server_error.create_response()
