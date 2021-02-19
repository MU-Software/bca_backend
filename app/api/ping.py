import flask.views

import app.api as api
import app.api.response_case as common_resp


class PingRoute(flask.views.MethodView, api.MethodViewMixin):
    def get(self):
        return common_resp.CommonResponseCase.ping_success.create_response()


resource_route = {
    '/ping': PingRoute
}
