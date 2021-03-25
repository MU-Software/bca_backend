#!/usr/bin/env python3.8
# -*- coding: UTF-8 -*-
import datetime
import email
import flask
import json
import math
import string
import time
import traceback
import typing
import unicodedata
import werkzeug

# ---------- Check and Normalize strings ----------
char_printable: str = string.ascii_letters + string.digits
char_printable     += string.punctuation  # noqa

char_urlsafe: str = string.ascii_letters + string.digits
char_urlsafe     += '-_'  # noqa

char_useridsafe: str = string.ascii_letters + string.digits


def normalize(s: str) -> str:
    return unicodedata.normalize('NFC', s)


def char_type(s):
    c_type = {
        'lower': string.ascii_lowercase,
        'upper': string.ascii_uppercase,
        'digit': string.digits,
        'punct': string.punctuation}
    for key, value in c_type.items():
        if s in value:
            return key
    return None


def get_str_char_types(target_str):
    str_char_type = list()
    for target_char in target_str:
        str_char_type.append(char_type(target_char))
    return list(set(str_char_type))


def is_email(s: str) -> bool:
    try:
        parsed_email = email.utils.parseaddr(s)[1]
        if parsed_email:
            if len(parsed_email.split('@')[1].split('.')) >= 2:
                return True
    except Exception:
        return False
    return False


def is_printable(s: str) -> bool:
    for c in s:
        if c not in char_printable:
            return False
    return True


def is_urlsafe(s: str) -> bool:
    for c in s:
        if c not in char_urlsafe:
            return False
    return True


def is_useridsafe(s: str) -> str:
    if 4 > len(s):
        return 'TOO_SHORT'
    if len(s) > 48:
        return 'TOO_LONG'

    for c in s:
        if c not in char_useridsafe:
            return 'FORBIDDEN_CHAR'

    return ''


def is_passwordsafe(s: str,
                    min_char_type_num: int = 2,
                    min_len: int = 8,
                    max_len: int = 1024) -> str:
    # Returnable case:
    #   '': OK.
    #   'TOO_LONG': Password is too long.
    #   'TOO_SHORT': Password is too short.
    #   'NEED_MORE_CHAR_TYPE': Password must have more char type.
    #   'FORBIDDEN_CHAR': Password has forbidden char type.
    if len(s) < min_len:
        return 'TOO_SHORT'
    if max_len < len(s):
        return 'TOO_LONG'

    s_char_type = get_str_char_types(s)
    if len(s_char_type) < min_char_type_num:
        return 'NEED_MORE_CHAR_TYPE'

    if not all(s_char_type):
        return 'FORBIDDEN_CHAR'

    return ''


# ---------- Standard statement to function ----------
def raise_(e) -> None:
    raise e


def get_traceback_msg(err):
    return ''.join(traceback.format_exception(
                   etype=type(err),
                   value=err,
                   tb=err.__traceback__))


# ---------- Elegant Pairing ----------
# http://szudzik.com/ElegantPairing.pdf
def elegant_pair(x, y) -> int:
    return x * x + x + y if x >= y else y * y + x


def elegant_unpair(z) -> tuple:
    sqrtz = math.floor(math.sqrt(z))
    sqz   = sqrtz * sqrtz  # noqa
    return (sqrtz, z - sqz - sqrtz) if (z - sqz) >= sqrtz\
           else (z - sqz, sqrtz)  # noqa


# ---------- Custom Exceptions ----------
def BackendException(code=500, data='',
                     backend_log=None, client_header=[],
                     description='Unexpected error happened. '
                                 'Contect to Administrator.',
                     json_prettier=None):
    # custom_headers should be list,
    # because we cannot make multiple items with same key in dict,
    # and setting Set-Cookie header multiple times is the case.
    if not isinstance(client_header, list):
        raise ValueError('client_header type must be list')

    # Enable JSON prettier when app is debug mode.
    json_prettier = 4 if flask.current_app.config.get('DEBUG', None) else None

    custom_headers = [('Content-Type', 'application/json; charset=utf-8'), ]
    if client_header:
        custom_headers += client_header

    body = {
        'IsSuccess': False,
        'status': code,
        'message': description,
        'data': data,
    }
    body_json = json.dumps(body, indent=json_prettier)

    err = werkzeug.exceptions.HTTPException()

    err.code = code
    err.description = description
    err.response = werkzeug.wrappers.response.Response(
                        body_json, code, custom_headers)

    err.get_body = lambda self, environ=None: body_json
    err.get_headers = lambda self, environ=None: custom_headers

    setattr(err, 'backend_log', backend_log)
    setattr(err, 'frost_exception', True)

    return err


# ---------- Time Calculator ----------
utc_desc   = lambda a, syntax='%Y/%m/%d %H:%M:%S': time.strftime(syntax, time.gmtime(a))  # noqa

date_to_time: typing.Callable[[int,], int] = lambda x: x * 24 * 60 * 60  # noqa
hour_to_time: typing.Callable[[int,], int] = lambda x: x      * 60 * 60  # noqa
update_rate: typing.Callable[[int,], int] = date_to_time(2) - hour_to_time(1)  # noqa

# ---------- Timezone ----------
UTC = datetime.timezone.utc
KST = datetime.timezone(datetime.timedelta(hours=9))


# ---------- Cookie Handler ----------
def cookie_creator(
        name: str, data: str, path: str = '/', domain: str = None,
        expires: str = None, maxage: int = None, never_expire: bool = False,
        samesite: str = 'strict', secure: bool = True, httponly: bool = True) -> str:
    if not any([expires, maxage, never_expire]):
        err_msg = 'At least one of the expires, maxage, never_expire'\
                  'should be set.'
        raise ValueError(err_msg)

    if never_expire:
        expires = 'Sat, 19 Jan 2038 04:14:07 GMT'

    header_cookie = list()
    header_cookie.append(f'{name}={data}')
    header_cookie.append(f'path={path}')

    if expires:
        header_cookie.append(f'Expires={expires}')
    else:
        header_cookie.append(f'Max-Age={maxage}')

    if domain:
        header_cookie.append(f'Domain={domain}')
    if samesite:
        header_cookie.append(f'SameSite={samesite}')
    if secure:
        header_cookie.append('secure')
    if httponly:
        header_cookie.append('HttpOnly')

    return '; '.join(header_cookie)


def user_cookie(data: str, secure: bool = True) -> str:
    return cookie_creator(
        'userJWT', data, path='/',
        never_expire=True, secure=secure
    )


def delete_cookie(name: str, path: str = '/', domain: str = '',
                  secure: bool = True, samesite: str = 'strict', httponly: bool = True) -> str:
    return cookie_creator(
        name, 'DUMMY', path=path, domain=domain,
        secure=secure, samesite=samesite, httponly=httponly,
        expires='Thu, 01 Jan 1970 00:00:00 GMT',
    )


def cookie_datetime(dt_time: datetime.datetime) -> str:
    if type(dt_time) != datetime.datetime:
        raise TypeError(f'a datetime object is required (got type {str(type(dt_time))})')

    dt_time = dt_time.replace(tzinfo=UTC)
    return dt_time.strftime("%a, %d %b %Y %H:%M:%S GMT")


# ---------- Request body parser Function ----------
def request_body(required_fields: list[str], optional_fields: list[str] = []) -> typing.Union[dict, list, None]:
    '''
    return type
        - dict: parsed request body
        - list: required but not contained fields
        - None: parse error
    '''
    try:
        req_body = flask.request.get_json(force=True)
        req_body = {k: v for k, v in req_body.items() if k and v}  # basic filter for empty keys and values

        # Check if all required fields are in
        if (not all([z in req_body.keys() for z in required_fields])):
            return [z for z in required_fields if z not in req_body]

        # Remove every field not in required and optional fields
        req_body = {k: req_body[k] for k in req_body if k in required_fields + optional_fields}

        return req_body
    except Exception:
        return None


# ---------- Helper Function ----------
def isiterable(in_obj):
    try:
        iter(in_obj)
        return True
    except Exception:
        return False


def ignore_exception(IgnoreException=Exception, DefaultVal=None):
    # from https://stackoverflow.com/a/2262424
    """ Decorator for ignoring exception from a function
    e.g.   @ignore_exception(DivideByZero)
    e.g.2. ignore_exception(DivideByZero)(Divide)(2/0)
    """
    def dec(function):
        def _dec(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except IgnoreException:
                return DefaultVal
        return _dec
    return dec


safe_int = ignore_exception(Exception, 0)(int)


# ---------- ETC ----------
pmmod_desc = lambda a: ''.join(y for x,y in zip([4&a,2&a,1&a], list('RWX')) if x)  # noqa


# ---------- Utility Classes ----------
class Singleton:
    __instance = None

    @classmethod
    def __getInstance(cls):
        return cls.__instance

    @classmethod
    def instance(cls, *args, **kargs):
        cls.__instance = cls(*args, **kargs)
        cls.instance = cls.__getInstance
        return cls.__instance


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)


class AutoRegisterClass:
    _subclasses = list()

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if not hasattr(cls, '_base_class') or not cls._base_class:
            raise ValueError('_base_class must be set')

        # Attributes will be shared with parent classes while inheriting them,
        # so _subclasses attribute must be cleared when new class is created.
        cls._subclasses = list()

        for base_cls in cls.__bases__:
            if base_cls.__name__ == cls._base_class:
                base_cls._subclasses.append(cls)
