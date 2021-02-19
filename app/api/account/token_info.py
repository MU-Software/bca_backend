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

        refresh_token_cookie = flask.request.cookies.get('refresh_token', '')
        access_token_cookie = flask.request.cookies.get('access_token', '')

        try:
            if refresh_token_cookie:
                refresh_token = jwt_module.RefreshToken.from_token(
                                    refresh_token_cookie,
                                    flask.current_app.config.get('SECRET_KEY'))
                result_dict['RefreshToken'] = {
                    'exp': refresh_token.exp
                }
        except Exception:
            result_header.append(('Set-Cookie', utils.delete_cookie('refresh_token')))

        if result_dict['RefreshToken'] is not None:
            try:
                if access_token_cookie:
                    access_token = jwt_module.AccessToken.from_token(
                                        access_token_cookie,
                                        flask.current_app.config.get('SECRET_KEY'))
                    result_dict['AccessToken'] = {
                        'exp': access_token.exp
                    }
            except Exception:
                result_header.append(('Set-Cookie', utils.delete_cookie('access_token')))
        else:
            result_header.append(('Set-Cookie', utils.delete_cookie('refresh_token')))

        return api.create_response(
            code=200, success=True,
            message='',
            data=result_dict, header=result_header)
