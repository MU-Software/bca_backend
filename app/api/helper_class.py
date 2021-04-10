import copy
import dataclasses
import flask
import functools
import inspect
import typing
import yaml

http_all_method = [
    'get', 'head', 'post', 'put',
    'delete', 'connect', 'options',
    'trace', 'patch']
ResponseType = tuple[typing.Any, int, tuple[tuple[str, str]]]


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


# Make request form
def create_response(
        success: bool = True,
        code: int = 200,
        sub_code: str = '',
        message: str = '',
        data: dict = {},
        header: tuple = (('', ''),),
        ):

    # Although we can guess whether request is success or not in status code,
    # the reason why we use success field is because of redirection(302).
    response = {
        'success': success,
        'code': code,
        'sub_code': sub_code,
        'message': message,
        'data': data
    }

    server_name = flask.current_app.config.get('BACKEND_NAME', 'MUsoftware Backend')

    result_header = (
        *header,
        # We don't need to add Content-Type: application/json here
        # because flask.jsonify will add it.

        # Add CORS header
        ('Server', server_name),
    )

    return (flask.jsonify(response), code, result_header)


@dataclasses.dataclass
class Response:
    description: str = ''
    code: int = 500
    public_sub_code: str = ''
    private_sub_code: str = ''
    success: bool = ''
    message: str = ''
    header: tuple[tuple[str, str]] = ()
    data: dict = dataclasses.field(default_factory=dict)

    def to_openapi_obj(self):
        return {
            'success': {
                'type': 'boolean',
                'enum': [self.success, ],
            },
            'code': {
                'type': 'integer',
                'enum': [self.code, ],
            },
            'sub_code': {
                'type': 'string',
                'enum': [self.public_sub_code, ],
            },
            'message': {
                'type': 'string',
            },
            'data': {
                'type': 'object',
                'enum': [self.data, ],
            }
        }

    def create_response(self,
                        header: tuple[tuple[str]] = (),
                        data: dict = {},
                        message: typing.Optional[str] = None) -> ResponseType:

        resp_header = (tuple(header.items()) if type(header) == dict else header)
        resp_header += (tuple(self.header.items()) if type(self.header) == dict else self.header)
        result_header = (
            *header,
            # We don't need to add Content-Type: application/json here
            # because flask.jsonify will add it.
            ('Server', flask.current_app.config.get('BACKEND_NAME', 'MUsoftware Backend')),
        )

        # TODO: Parse YAML file and get response message using public_sub_code
        resp_data = copy.deepcopy(data)
        resp_data.update(data)
        response_body = {
            'success': self.success,
            'code': self.code,
            'sub_code': self.public_sub_code,
            'message': message or self.message,
            'data': resp_data
        }

        return (flask.jsonify(response_body), self.code, result_header)


class ResponseCaseCollector(AutoRegisterClass):
    _base_class = 'ResponseCaseCollector'


from app.api.response_case import CommonResponseCase  # noqa


class MethodViewMixin(AutoRegisterClass):
    _base_class = 'MethodViewMixin'

    def options(self):
        all_mtd = inspect.getmembers(self, predicate=inspect.ismethod)
        http_mtd = [z[0] for z in all_mtd if z[0] in http_all_method]  # z[1] is method itself

        return CommonResponseCase.http_ok.create_response(
            header=(
                ('Allow', ', '.join(http_mtd)),
            ))


class RequestHeader:
    def __init__(self, required_fields: dict[str, dict[str, str]], optional_fields: dict[str, dict[str, str]] = dict()):
        self.req_header: dict = dict()
        self.required_fields: dict[str, dict[str, str]] = required_fields
        self.optional_fields: dict[str, dict[str, str]] = optional_fields

    def __call__(self, func: typing.Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                self.req_header = flask.request.headers
                # Filter for empty keys and values
                self.req_header = {k: v for k, v in self.req_header.items() if k and v}

                # Check if all required fields are in
                if (not all([z in self.req_header.keys() for z in self.required_fields])):
                    return CommonResponseCase.header_required_omitted.create_response(
                        data={
                            'lacks': [z for z in self.required_fields if z not in self.req_header]
                        }
                    )

            except Exception:
                return CommonResponseCase.header_invalid.create_response()

            kwargs['req_header'] = self.req_header
            return func(*args, **kwargs)

        # Parse docstring and inject requestBody data
        if doc_str := inspect.getdoc(func):
            doc_data: dict = yaml.safe_load(doc_str)
            if 'parameters' not in doc_data:
                doc_data['parameters'] = []

            parm_collector: list = list()
            for k, v in self.required_fields.items():
                field_data = {
                    'in': 'header',
                    'name': k,
                    'required': True
                }
                if 'description' in v:
                    field_data['description'] = v['description']

                if 'type' in v:
                    field_data['schema'] = {'type': v['type'], }

                parm_collector.append(field_data)

            for k, v in self.optional_fields.items():
                field_data = {
                    'in': 'header',
                    'name': k,
                }
                if 'description' in v:
                    field_data['description'] = v['description']

                if 'type' in v:
                    field_data['schema'] = {'type': v['type'], }

                parm_collector.append(field_data)

            doc_data['parameters'] += parm_collector

            func.__doc__ = yaml.safe_dump(doc_data)
            wrapper.__doc__ = yaml.safe_dump(doc_data)

        return wrapper


class RequestBody:
    def __init__(self, required_fields: dict[str, dict[str, str]], optional_fields: dict[str, dict[str, str]] = dict()):
        self.req_body: dict = dict()
        self.required_fields: dict[str, dict[str, str]] = required_fields
        self.optional_fields: dict[str, dict[str, str]] = optional_fields

    def __call__(self, func: typing.Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                self.req_body = flask.request.get_json(force=True)
                # Filter for empty keys and values
                self.req_body = {k: v for k, v in self.req_body.items() if k and v}

                # Check if all required fields are in
                if (not all([z in self.req_body.keys() for z in self.required_fields])):
                    return CommonResponseCase.body_required_omitted.create_response(
                        data={
                            'lacks': [z for z in self.required_fields if z not in self.req_body]
                        }
                    )

                # Remove every field not in required and optional fields
                self.req_body = {k: self.req_body[k] for k in self.req_body
                                 if k in list(self.required_fields.keys()) + list(self.optional_fields.keys())}
                if self.required_fields and not self.req_body:
                    return CommonResponseCase.body_empty.create_response()

            except Exception:
                return CommonResponseCase.body_invalid.create_response()

            kwargs['req_body'] = self.req_body
            return func(*args, **kwargs)

        # Parse docstring and inject requestBody data
        if doc_str := inspect.getdoc(func):
            doc_data: dict = yaml.safe_load(doc_str)
            if 'requestBody' not in doc_data:
                doc_data['requestBody'] = {
                    'content': {
                        'application/json': {
                            'schema': {
                                'type': 'object',
                                'properties': {},
                                'required': [],
                            }
                        }
                    }
                }

            properties: dict = dict()
            required: list = list()
            for k, v in self.required_fields.items():
                properties[k] = v
                required.append(k)
            for k, v in self.optional_fields.items():
                properties[k] = v

            doc_data['requestBody']['content']['application/json']['schema']['properties'].update(properties)
            doc_data['requestBody']['content']['application/json']['schema']['required'] += required

            if not doc_data['requestBody']['content']['application/json']['schema']['required']:
                doc_data['requestBody']['content']['application/json']['schema'].pop('required')

            func.__doc__ = yaml.safe_dump(doc_data)
            wrapper.__doc__ = yaml.safe_dump(doc_data)

        return wrapper
