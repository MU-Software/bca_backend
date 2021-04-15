import flask
import os

restapi_version = os.environ.get('RESTAPI_VERSION')


def init_app(app: flask.Flask):
    @app.route(f'/api/{restapi_version}/debug/<path:path>')
    def static_route(path):
        return flask.send_from_directory('static/debug', path)


import app.api.debug.decorator_debug as decorator_debug  # noqa

resource_route = {
    f'/api/{restapi_version}/debug/decorator/test/<string:debug_id>': decorator_debug.Debug__DecoratorRoute,
    f'/api/{restapi_version}/debug/decorator/need-signout': decorator_debug.Debug_UserMustSignOut_DecoratorRoute,
}
