import flask

import app.api.helper_class as api_class
import app.common.decorator as deco_module


class Debug__DecoratorRoute(flask.views.MethodView):
    @deco_module.PERMISSION(deco_module.test_deco, perm_args={'qwe': 'asd'})
    def get(self, debug_id: str = None) -> api_class.ResponseType:
        return api_class.create_response(
            code=200, success=True,
            message={
                'debug_id': debug_id,
            })


class Debug_UserMustSignOut_DecoratorRoute(flask.views.MethodView):
    @deco_module.PERMISSION(deco_module.need_signed_out)
    def get(self) -> api_class.ResponseType:
        return api_class.create_response(
            code=200, success=True,
            message='')
