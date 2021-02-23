import flask
import flask.views

import app.api as api
import app.common.utils as utils
import app.database as db_module
import app.database.jwt as jwt_module

db = db_module.db


class TokenInfoRoute(flask.views.MethodView, api.MethodViewMixin):
    def get(self):
        result_dict = {
            'AccessToken': None,
            'RefreshToken': None
        }
        result_header = []

        refresh_token_request_cookie = flask.request.cookies.get('refresh_token', '')
        access_token_request_cookie = flask.request.cookies.get('access_token', '')

        refresh_token_remover_cookie = utils.delete_cookie(
                                            name='refresh_token',
                                            path=f'/api/{api.restapi_version}/account',
                                            domain=api.server_name if api.restapi_version != 'dev' else None,
                                            samesite='None' if api.restapi_version == 'dev' else 'strict',
                                            secure=True)
        access_token_remover_cookie = utils.delete_cookie(
                                            name='access_token',
                                            path='/',
                                            domain=api.server_name if api.restapi_version != 'dev' else None,
                                            samesite='None' if api.restapi_version == 'dev' else 'strict',
                                            secure=True)
        refresh_token_remover_header = ('Set-Cookie', refresh_token_remover_cookie)
        access_token_remover_header = ('Set-Cookie', access_token_remover_cookie)

        try:
            if refresh_token_request_cookie:
                refresh_token = jwt_module.RefreshToken.from_token(
                                    refresh_token_request_cookie,
                                    flask.current_app.config.get('SECRET_KEY'))
                result_dict['RefreshToken'] = {
                    'exp': refresh_token.exp,
                    'userUUID': refresh_token.user,
                    'username': refresh_token.usertable.id,
                    'nickname': refresh_token.usertable.nickname,
                    'profileImageURL': refresh_token.usertable.profile_image,
                }

                if access_token_request_cookie:
                    try:
                        access_token = jwt_module.AccessToken.from_token(
                                            access_token_request_cookie,
                                            flask.current_app.config.get('SECRET_KEY'))
                        result_dict['AccessToken'] = {'exp': access_token.exp}
                    except Exception:
                        result_header.append(access_token_remover_header)
            else:
                result_header.append(refresh_token_remover_header)
                result_header.append(access_token_remover_header)
        except Exception as err:
            print(utils.get_traceback_msg(err), flush=True)
            result_header.append(refresh_token_remover_header)
            result_header.append(access_token_remover_header)

        return api.create_response(
            code=200, success=True,
            message='',
            data=result_dict, header=result_header)
