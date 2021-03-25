import app.api as api
import app.common.utils as utils

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
header_collection: dict[str, tuple[str, str]] = {
    'delete_refresh_token': (
        ('Set-Cookie', refresh_token_remover_cookie),
    ),
    'delete_access_token': (
        ('Set-Cookie', access_token_remover_cookie),
    ),
    'delete_all_tokens': (
        ('Set-Cookie', refresh_token_remover_cookie),
        ('Set-Cookie', access_token_remover_cookie),
    ),
}


class AccountResponseCase(api.ResponseCaseCollector):
    # User related
    user_not_found = api.Response(
        code=404, success=False,
        public_sub_code='user.not_found')
    user_not_signed_in = api.Response(
        code=401, success=False,
        public_sub_code='user.not_signed_in',
        header=header_collection['delete_all_tokens'])

    # Sign Up related
    user_signed_up = api.Response(  # User signing up success
        code=201, success=True,
        public_sub_code='user.sign_up')
    user_signed_up_but_mail_error = api.Response(  # User signing up success, but sign-up mail did not sent
        code=201, success=True,
        public_sub_code='user.sign_up_but_mail_error')

    user_safe_to_use = api.Response(
        # When user-wanted nick/id/email address can be used because no one isn't using them
        code=200, success=False,
        public_sub_code='user.safe_to_use')
    user_already_used = api.Response(  # When there is a user that has user-wanted nick/id/email
        code=401, success=False,
        public_sub_code='user.already_used',
        data={'duplicate': []})
    user_info_mismatch = api.Response(
        code=401, success=False,
        public_sub_code='user.info_mismatch',
        data={'fields': []})

    # Sign In related
    user_signed_in = api.Response(  # User signing in success
        code=200, success=True,
        public_sub_code='user.sign_in')
    user_wrong_password = api.Response(
        code=401, success=False,
        public_sub_code='user.wrong_password',
        data={'left_chance': 0})
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
