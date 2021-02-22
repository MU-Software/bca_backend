import dataclasses
import flask
import flask_cors
import inspect
import os
import typing

import app.common.utils as utils

http_all_method = [
    'get', 'head', 'post', 'put',
    'delete', 'connect', 'options',
    'trace', 'patch']
ResponseType = tuple[typing.Any, int, tuple[tuple[str, str]]]

# I had to get these values from env,
# because We can initialize these values from flask config only on app context,
# and some modules already got these values before initialization.
restapi_version: str = os.environ.get('RESTAPI_VERSION')
server_name: str = os.environ.get('SERVER_NAME')


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


class ResponseCaseCollector(utils.AutoRegisterClass):
    _base_class = 'ResponseCaseCollector'


@dataclasses.dataclass
class Response:
    code: int = 500
    public_sub_code: str = ''
    private_sub_code: str = ''
    success: bool = ''
    message: str = ''
    header: tuple[tuple[str, str]] = ()
    data: dict = dataclasses.field(default_factory=dict)

    def create_response(self, header: tuple[tuple[str]] = (), data: dict = {}) -> ResponseType:
        # TODO: Parse YAML file and get response message using public_sub_code
        resp_message = ''

        return create_response(
            success=self.success,
            code=self.code,
            sub_code=self.public_sub_code,
            header=header+self.header,
            data=self.data | data,  # Dict union@Python 3.9
            message=resp_message)


from app.api.response_case import CommonResponseCase  # noqa


class MethodViewMixin:
    def options(self):
        all_mtd = inspect.getmembers(self, predicate=inspect.ismethod)
        http_mtd = [z[0] for z in all_mtd if z[0] in http_all_method]  # z[1] is method itself

        return CommonResponseCase.http_ok.create_response(
            header=(
                ('Allow', ', '.join(http_mtd)),
            ))


resource_routes: dict = {}
import app.api.account as route_account  # noqa
resource_routes.update(route_account.resource_route)
import app.api.ping as route_ping  # noqa
resource_routes.update(route_ping.resource_route)
import app.api.posts as route_posts  # noqa
resource_routes.update(route_posts.resource_route)

if flask.current_app.config.get('RESTAPI_VERSION') == 'dev':
    import app.api.debug as route_debug  # noqa
    resource_routes.update(route_debug.resource_route)


# Register views and handlers to app
def init_app(app: flask.Flask):
    global restapi_version
    restapi_version = app.config.get('RESTAPI_VERSION')

    app.url_map.strict_slashes = False
    flask_cors.CORS(app)

    import app.api.request_handler as req_handler  # noqa
    req_handler.register_request_handler(app)
    if app.config.get('DEBUG', False):
        import app.api.debug as debug_route
        debug_route.init_app(app)

    for path, route_model in resource_routes.items():
        view_name = route_model.__name__
        view_func = route_model.as_view(view_name)
        app.add_url_rule('/' + restapi_version + path, view_func=view_func)
