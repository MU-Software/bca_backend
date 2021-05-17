import flask
import flask_cors
import flask_limiter
import flask_limiter.util
import os

# I had to get these values from env,
# because We can initialize these values from flask config only on app context,
# and some modules already got these values before initialization.
restapi_version: str = os.environ.get('RESTAPI_VERSION')
server_name: str = os.environ.get('SERVER_NAME')

rate_limiter: flask_limiter.Limiter = None

resource_routes: dict = {}
import app.api.ping as route_ping  # noqa
resource_routes.update(route_ping.resource_route)
import app.api.account as route_account  # noqa
resource_routes.update(route_account.resource_route)
import app.api.profiles as route_profile  # noqa
resource_routes.update(route_profile.resource_route)
import app.api.sync as route_sync  # noqa
resource_routes.update(route_sync.resource_route)


if flask.current_app.config.get('RESTAPI_VERSION') == 'dev':
    import app.api.debug as route_debug  # noqa
    resource_routes.update(route_debug.resource_route)


# Register views and handlers to app
def init_app(app: flask.Flask):
    global restapi_version
    restapi_version = app.config.get('RESTAPI_VERSION')
    app.url_map.strict_slashes = False

    allowed_origins: list = [f'https://{app.config.get("SERVER_NAME")}']
    local_client_port = app.config.get('LOCAL_DEV_CLIENT_PORT')
    if restapi_version == 'dev' and local_client_port:
        allowed_origins.append(f'http://localhost:{local_client_port}')

    flask_cors.CORS(app, resources={
        r'*': {
            'origins': allowed_origins,
            'supports_credentials': True,
        }})

    global rate_limiter
    rate_limiter = flask_limiter.Limiter(app, key_func=flask_limiter.util.get_remote_address)

    import app.api.request_handler as req_handler  # noqa
    req_handler.register_request_handler(app)
    if app.config.get('DEBUG', False):
        import app.api.debug as debug_route
        debug_route.init_app(app)

    for path, route_model in resource_routes.items():
        view_name = route_model.__name__
        view_func = route_model.as_view(view_name)
        app.add_url_rule('/api/' + restapi_version + path, view_func=view_func)
