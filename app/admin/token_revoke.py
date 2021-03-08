import datetime
import flask
import flask_admin as fadmin

import app.api as api
import app.database as db_module
import app.database.user as user
import app.database.jwt as jwt_module

db = db_module.db
redis_db = db_module.redis_db


class Admin_TokenRevoke_View(fadmin.BaseView):
    @fadmin.expose('/', methods=('GET',))
    def index(self):
        user_result = user.User.query.all()
        token_result = jwt_module.RefreshToken.query.all()
        revoked_dict = dict()
        for k, v in redis_db.scan_iter(pattern='refresh_revoke=*'):
            revoked_dict[k.decode()] = v.decode()

        return self.render(
                    'admin/token_revoke.html',
                    user_result=user_result,
                    token_result=token_result,
                    revoked_result=revoked_dict)

    @fadmin.expose('/', methods=('POST',))
    def post(self):
        try:
            revoke_req = flask.request.get_json(force=True)
            revoke_req = {k: v for k, v in revoke_req.items() if v}
            if not ('user_uuid' in revoke_req or 'target_jti' in revoke_req):
                raise Exception
        except Exception:
            return api.create_response(
                code=400,
                success=False,
                message='Wrong request body data - JSON decode failed')

        if 'user_uuid' in revoke_req:
            query_result = jwt_module.RefreshToken.query\
                                .join(jwt_module.RefreshToken.usertable, aliased=True)\
                                .filter_by(uuid=int(revoke_req['user_uuid'])).all()
            if not query_result:
                return api.create_response(
                    code=404,
                    success=False,
                    message='User or JWT that mapped to that user not found')

            for target in query_result:
                # TODO: set can set multiple at once, so use that method instead
                redis_db.set('refresh_revoke=' + str(target.jti), 'revoked', datetime.timedelta(weeks=2))
        else:
            query_result = jwt_module.RefreshToken.query\
                                .filter(jwt_module.RefreshToken.jti == int(revoke_req['target_jti']))\
                                .all()  # noqa
            if not query_result:
                return api.create_response(
                    code=404,
                    success=False,
                    message='RefreshToken that has such JTI not found')

            redis_db.set('refresh_revoke=' + str(revoke_req['target_jti']), 'revoked', datetime.timedelta(weeks=2))

        return api.create_response(
            code=301, success=True,
            message='OK',
            header=(
                ('Location', '/admin/token-revoke'),
            ))
