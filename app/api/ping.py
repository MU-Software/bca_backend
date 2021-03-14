import flask.views

import app.api as api
from app.api.response_case import CommonResponseCase


class PingRoute(flask.views.MethodView, api.MethodViewMixin):
    def get(self):
        return CommonResponseCase.ping_success.create_response()


resource_route = {
    '/ping': PingRoute
}
