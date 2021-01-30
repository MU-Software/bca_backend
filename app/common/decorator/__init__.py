import functools
import typing

import app.api as api
from .auth import *  # noqa


def NOT_DONE(func):
    def decorated(*args, **kwargs):
        return api.create_response(
            code=501, success=False,
            message='We didn\'t finish writing this method, '
                    'so this method must not be called.')
    return decorated


def PERMISSION(perm, perm_args=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> api.ResponseType:
            perm_args_dict = {'fkwargs': kwargs}
            if perm_args:
                perm_args_dict['perm_args'] = perm_args

            # permission test function must return
            # <test check result> and <None | <response when check test fails>>
            perm_test_result: tuple[bool, typing.Optional[api.ResponseType]] = perm(**perm_args_dict)
            return func(*args, **kwargs) if perm_test_result[0] else perm_test_result[1]

        setattr(wrapper, 'permission', perm)
        return wrapper
    return decorator
