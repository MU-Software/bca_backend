import flask
import flask.views
import app.api as api
import app.database as db_module
# import app.database.jwt as jwt_module

db = db_module.db


class AccountDuplicateCheckRoute(flask.views.MethodView):
    def post(self):
        # TODO: Duplicate check about post request data
        return api.create_response(
            code=200, success=True,
            message='',
            data={

            })
