import app.api as api
import app.common.utils as utils

header_collection: dict[str, tuple[str, str]] = {
    'delete_refresh_token': (
        ('Set-Cookie', utils.delete_cookie('refresh_token', f'/{api.restapi_version}/account')),
    ),
    'delete_access_token': (
        ('Set-Cookie', utils.delete_cookie('access_token')),
    ),
    'delete_all_tokens': (
        ('Set-Cookie', utils.delete_cookie('refresh_token', f'/{api.restapi_version}/account')),
        ('Set-Cookie', utils.delete_cookie('access_token')),
    ),
}


class AccountResponseCase(api.ResponseCaseCollector):
    # User related
    user_not_found = api.Response(
        code=404, success=False,
        public_sub_code='user.not_found')
    user_not_logged_in = api.Response(
        code=401, success=False,
        public_sub_code='user.not_signed_in',
        header=header_collection['delete_all_tokens'])

    # Sign Up related
    user_signed_up = api.Response(  # User signing up success
        code=201, success=True,
        public_sub_code='user.sign_up')
    user_already_used = api.Response(
        code=401, success=False,
        public_sub_code='user.already_used',
        data={'duplicate': []})

    # Sign In related
    user_signed_in = api.Response(  # User signing in success
        code=200, success=True,
        public_sub_code='user.sign_in')
    user_wrong_password = api.Response(
        code=401, success=False,
        public_sub_code='user.wrong_password')
    user_locked = api.Response(
        code=401, success=False,
        public_sub_code='user.locked',
        data={'reason': ''})
    user_deactivated = api.Response(
        code=401, success=False,
        public_sub_code='user.deactivated',
        data={'reason': ''})

    # Sign Out related
    user_signed_out = api.Response(
        code=200, success=True,
        public_sub_code='user.sign_out',
        header=header_collection['delete_all_tokens'])

    # Access Token related
    access_token_refreshed = api.Response(  # Access token refreshing success
        code=200, success=True,
        public_sub_code='access_token.refreshed')
    access_token_invalid = api.Response(
        code=401, success=False,
        public_sub_code='access_token.invalid',
        header=header_collection['delete_access_token'])
    access_token_expired = api.Response(
        code=401, success=False,
        public_sub_code='access_token.expired',
        header=header_collection['delete_access_token'])

    # Refresh Token related
    refresh_token_invalid = api.Response(
        code=401, success=False,
        public_sub_code='refresh_token.invalid',
        header=header_collection['delete_all_tokens'])
    refresh_token_expired = api.Response(
        code=401, success=False,
        public_sub_code='refresh_token.expired',
        header=header_collection['delete_all_tokens'])
