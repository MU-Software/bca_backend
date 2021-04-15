import datetime
import flask_admin as fadmin

import app.api.helper_class as api_class
import app.database as db_module
import app.database.user as user
import app.database.jwt as jwt_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db
redis_db = db_module.redis_db


class Admin_TokenRevoke_View(fadmin.BaseView):
    @fadmin.expose('/', methods=('GET',))
    def index(self):
        user_result = user.User.query.all()
        token_result = jwt_module.RefreshToken.query.all()
        revoked_dict = dict()
        for k, v in redis_db.scan_iter(match='refresh_revoke=*'):
            revoked_dict[k.decode()] = v.decode()

        return self.render(
                    'admin/token_revoke.html',
                    user_result=user_result,
                    token_result=token_result,
                    revoked_result=revoked_dict)

    @fadmin.expose('/', methods=('POST',))
    @api_class.RequestBody(
        required_fields={},
        optional_fields={
            'user_uuid': {'type': 'integer', },
            'target_jti': {'type': 'integer', },
        })
    def post(self, req_body: dict):
        if not any((('user_uuid' in req_body), ('target_jti' in req_body))):
            CommonResponseCase.body_required_omitted.create_response(
                message='Need user_uuid or target_jti',
                data={'lacks': ['user_uuid', 'target_jti']})

        if 'user_uuid' in req_body:
            # How this goddamn query works?!
            query_result = jwt_module.RefreshToken.query\
                                .join(jwt_module.RefreshToken.usertable, aliased=True)\
                                .filter_by(uuid=int(req_body['user_uuid'])).all()
            if not query_result:
                return AccountResponseCase.user_not_found.create_response(
                    message='User or JWT that mapped to that user not found')

            for target in query_result:
                # TODO: set can set multiple at once, so use that method instead
                redis_db.set('refresh_revoke=' + str(target.jti), 'revoked', datetime.timedelta(weeks=2))
        else:
            query_result = jwt_module.RefreshToken.query\
                                .filter(jwt_module.RefreshToken.jti == int(req_body['target_jti']))\
                                .all()  # noqa
            if not query_result:
                return AccountResponseCase.refresh_token_invalid(
                    message='RefreshToken that has such JTI not found')

            redis_db.set('refresh_revoke=' + str(req_body['target_jti']), 'revoked', datetime.timedelta(weeks=2))

        return CommonResponseCase.http_ok.create_response(
            code=301,
            header=(
                ('Location', '/admin/token-revoke'),
            ))
