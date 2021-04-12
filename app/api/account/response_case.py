import os
import copy

import app.api.helper_class as api_class
import app.common.utils as utils

server_name = os.environ.get('SERVER_NAME')
restapi_version = os.environ.get('RESTAPI_VERSION')

refresh_token_remover_cookie = utils.delete_cookie(
                                    name='refresh_token',
                                    path=f'/api/{restapi_version}/account',
                                    domain=server_name if restapi_version != 'dev' else None,
                                    samesite='None' if restapi_version == 'dev' else 'strict',
                                    secure=True)
delete_refresh_token: tuple[str, str] = ('Set-Cookie', refresh_token_remover_cookie)

user_auth_data_template: dict = {
            'email': '', 'id': '',
            'nick': '', 'uuid': 0,
            'profileImageURL': '',

            'refresh_token': {'exp': 'DATETIME', },
            'access_token': {
                'token': '',
                'exp': 'DATETIME',
            },
        }


class AccountResponseCase(api_class.ResponseCaseCollector):
    # User related
    user_not_found = api_class.Response(
        description='We cannot find any users',
        code=404, success=False,
        public_sub_code='user.not_found')
    user_not_signed_in = api_class.Response(
        description='User is not signed in.',
        code=401, success=False,
        public_sub_code='user.not_signed_in',
        header=delete_refresh_token)

    # Sign Up related
    user_signed_up = api_class.Response(  # User signing up success
        description='Successfully created a new account. Welcome!',
        code=201, success=True,
        public_sub_code='user.sign_up',
        data=copy.deepcopy(user_auth_data_template))
    user_signed_up_but_mail_error = api_class.Response(  # User signing up success, but sign-up mail did not sent
        description='Successfully created a new account, but we couldn\'t send a confirmation mail.',
        code=201, success=True,
        public_sub_code='user.sign_up_but_mail_error')

    user_safe_to_use = api_class.Response(
        description='No one isn\'t using user-wanted nick/id/email address, so you can use it.',
        code=200, success=False,
        public_sub_code='user.safe_to_use')
    user_already_used = api_class.Response(
        description='Someone is already using user-wanted nick/id/email address. Try another one.',
        code=401, success=False,
        public_sub_code='user.already_used',
        data={'duplicate': ['', ]})
    user_info_mismatch = api_class.Response(
        description='We can\'t do what you request because the data you sent isn\'t correct.',
        code=401, success=False,
        public_sub_code='user.info_mismatch',
        data={'fields': ['', ]})

    # Sign In related
    user_signed_in = api_class.Response(
        description='User successfully signed in.',
        code=200, success=True,
        public_sub_code='user.sign_in',
        data=copy.deepcopy(user_auth_data_template))
    user_wrong_password = api_class.Response(
        description='User typed wrong password.',
        code=401, success=False,
        public_sub_code='user.wrong_password',
        data={'left_chance': 0})
    user_locked = api_class.Response(
        description='Account you requested is locked.',
        code=401, success=False,
        public_sub_code='user.locked',
        data={'reason': ''})
    user_deactivated = api_class.Response(
        description='Account you requested is deactivated.',
        code=401, success=False,
        public_sub_code='user.deactivated',
        data={'reason': ''})

    # Sign Out related
    user_signed_out = api_class.Response(
        description='User signed out.',
        code=200, success=True,
        public_sub_code='user.sign_out',
        header=delete_refresh_token)

    # Account deactivate
    user_deactivate_success = api_class.Response(
        description='Successfully deactivated a account. This is different with user_deactivated.',
        code=204, success=True,
        public_sub_code='user.deactivate_success',
        message='Goodbye, Dear Friend!')

    # Email auth related
    email_token_not_given = api_class.Response(
        description='Email token is not provided on URL',
        code=400, success=False,
        public_sub_code='email.empty',
        message='Email token is not provided')
    email_expired = api_class.Response(
        description='Email is expired.',
        code=410, success=False,
        public_sub_code='email.expired',
        message='Email is expired.')
    email_invalid = api_class.Response(
        description='Token in Email is invalid.',
        code=410, success=False,
        public_sub_code='email.invalid',
        message='Token in Email is invalid.')
    email_not_found = api_class.Response(
        description='Token in Email is not found on DB.',
        code=404, success=False,
        public_sub_code='email.not_found',
        message='Token in Email is invalid.')
    email_success = api_class.Response(
        description='Email Action done successfully.',
        code=200, success=True,
        public_sub_code='email.success',
        message='Email Action done successfully.')

    # Access Token related
    access_token_refreshed = api_class.Response(  # Access token refreshing success
        description='Access token refreshed.',
        code=200, success=True,
        public_sub_code='access_token.refreshed',
        data=copy.deepcopy(user_auth_data_template))
    access_token_invalid = api_class.Response(
        description='Access token is invalid.',
        code=401, success=False,
        public_sub_code='access_token.invalid')
    access_token_expired = api_class.Response(
        description='Access token is expired. Please refresh it.',
        code=401, success=False,
        public_sub_code='access_token.expired')

    # Refresh Token related
    refresh_token_invalid = api_class.Response(
        description='Refresh token is invalid. Please re-signin.',
        code=401, success=False,
        public_sub_code='refresh_token.invalid',
        header=[delete_refresh_token, ])
    refresh_token_expired = api_class.Response(
        description='Refresh token is expired. Please re-signin.',
        code=401, success=False,
        public_sub_code='refresh_token.expired',
        header=[delete_refresh_token, ])
