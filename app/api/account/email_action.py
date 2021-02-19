import flask
import flask.views
import jwt

import app.api as api
import app.database as db_module
import app.database.user as user

db = db_module.db


class EmailActionRoute(flask.views.MethodView, api.MethodViewMixin):
    def get(self, email_token: str):
        if not email_token:
            return api.create_response(
                code=400, success=False,
                message='Email token is not provided')

        try:
            jwt_token = jwt.decode(email_token, key=flask.current_app.config.get('SECRET_KEY'), algorithms='HS256')
        except jwt.exceptions.ExpiredSignatureError:
            return api.create_response(
                code=400, success=False,
                message='Your email has expired')
        except jwt.exceptions.DecodeError as err:
            import traceback
            print(''.join(traceback.format_exception(etype=type(err), value=err, tb=err.__traceback__)))
            return api.create_response(
                code=400, success=False,
                message='Your email is invalid-a')

        target_user: user.User = user.User.query.filter(user.User.uuid == jwt_token['user']).first()
        if not target_user:
            return api.create_response(
                code=400, success=False,
                message='Your email is invalid-b')

        if target_user.email_secret != email_token:
            return api.create_response(
                code=400, success=False,
                message='Your email is invalid-c')

        # OK, now we can assumes that email is verified,
        # Do what token says.
        if jwt_token['data']['action'] == 'EMAIL_VERIFY':
            target_user.email_verified = True
            target_user.email_secret = None
            db.session.commit()

            return api.create_response(
                code=200, success=True,
                message='Your email is now verified')

        return api.create_response(
            code=400, success=False,
            message='Your email is invalid-d')
