# PERMISSION testing decorator definition
# - Usage
#     - @deco_module.PERMISSON(deco_module.<permission_test_function>, perm_args=<dict>)
# - All test functions can get these arguments...
#     - perm_args: Parameters that specifies on PERMISSION decorator, see above.
#     - fkwargs: Dictionary that will be send to route methods like get or post, such as post_id.
# - All test functions must return...
#     - Boolean
#     - None | api_class.ResponseType
import flask
import jwt
import typing

import app.api.helper_class as api_class
import app.database.jwt as jwt_module


def test_deco(perm_args: typing.Any, fkwargs: dict) -> tuple[bool, api_class.ResponseType]:
    print(perm_args)
    print(fkwargs)
    return True, None


def need_signed_out(perm_args: typing.Any = None, fkwargs: dict = None) -> tuple[bool, api_class.ResponseType]:
    refresh_token_cookie = flask.request.cookies.get('refresh_token', '')
    access_token_cookie = flask.request.cookies.get('access_token', '')

    # This function must be used only in /account route,
    # Because refresh token can be accessed only in /account route
    if not flask.request.path.startswith(f'/api/{flask.current_app.config.get("RESTAPI_VERSION")}/account'):
        # But, if this function used in non-/account-route, then always return 401,
        # because we can't check whether we are signed-in or not.
        return False, api_class.create_response(
                code=401, success=False,
                message='Cannot determine whether user signed in or not')

    if refresh_token_cookie or access_token_cookie:
        try:
            jwt_module.RefreshToken.from_token(
                refresh_token_cookie,
                flask.current_app.config.get('SECRET_KEY'))
            return False, api_class.create_response(
                code=401, success=False,
                message='User must be signed out')
        except Exception:
            return True, None
    else:
        return True, None


def need_access_token(perm_args: typing.Any = None, fkwargs: dict = None) -> tuple[bool, api_class.ResponseType]:
    access_token_cookie = flask.request.cookies.get('access_token', '')
    if not access_token_cookie:
        return False, api_class.create_response(
            code=401, success=False,
            message='No access token given')

    try:
        jwt_module.AccessToken.from_token(
            access_token_cookie,
            flask.current_app.config.get('SECRET_KEY'))
    except jwt.exceptions.ExpiredSignatureError:
        return False, api_class.create_response(
            code=401, success=False,
            message='Access Token is too old')
    except jwt.exceptions.InvalidTokenError as err:
        if err.message == 'This token was revoked':
            return False, api_class.create_response(
                code=401, success=False,
                message='Access Token is revoked')
        return False, api_class.create_response(
            code=401, success=False,
            message='Access Token is invalid')
    except Exception:
        return False, api_class.create_response(
            code=401, success=False,
            message='Access Token is invalid-e')

    return True, None
