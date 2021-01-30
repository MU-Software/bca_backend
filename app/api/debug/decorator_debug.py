import flask

import app.api as api
import app.common.decorator as deco_module


class Debug__DecoratorRoute(flask.views.MethodView):
    @deco_module.PERMISSION(deco_module.test_deco, perm_args={'qwe': 'asd'})
    def get(self, debug_id: str = None) -> api.ResponseType:
        return api.create_response(
            code=200, success=True,
            message={
                'debug_id': debug_id,
            })


class Debug_UserMustSignOut_DecoratorRoute(flask.views.MethodView):
    @deco_module.PERMISSION(deco_module.need_signed_out)
    def get(self) -> api.ResponseType:
        return api.create_response(
            code=200, success=True,
            message='')
