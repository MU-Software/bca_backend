import flask
import flask.views

import app.api as api
import app.common.utils as utils
import app.database as db_module
import app.database.user as user_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase

db = db_module.db


class AccountDuplicateCheckRoute(flask.views.MethodView, api.MethodViewMixin):
    def post(self):
        # Check duplicates about posted request data
        dupcheck_req = utils.request_body(
                            required_fields=[],
                            optional_fields=['email', 'id', 'nickname'])
        if type(dupcheck_req) == list:
            return CommonResponseCase.body_required_omitted.create_response(data={'lacks': dupcheck_req})
        elif dupcheck_req is None:
            return CommonResponseCase.body_invalid.create_response()
        elif not dupcheck_req:
            return CommonResponseCase.body_empty.create_response()
        elif type(dupcheck_req) != dict:
            return CommonResponseCase.body_invalid.create_response()

        dupcheck_req: dict = {k: db.func.lower(utils.normalize(dupcheck_req[k])) if k != 'nickname'
                              else dupcheck_req[k] for k in dupcheck_req}

        field_column_map = {
            'email': user_module.User.email,
            'id': user_module.User.id,
            'nickname': user_module.User.nickname,
        }
        check_result = list()
        try:
            for field_name, field_value in dupcheck_req.items():
                if user_module.User.query.filter(field_column_map[field_name] == field_value).first():
                    check_result.append(field_name)

            if check_result:
                return AccountResponseCase.user_already_used.create_response(data={
                    'duplicate': check_result
                })
            return AccountResponseCase.user_safe_to_use.create_response()
        except Exception:
            return CommonResponseCase.server_error.create_response()
