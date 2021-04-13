import flask

import app.api.helper_class as api_class
import app.database as db_module
import app.database.user as user_module
import app.database.jwt as jwt_module
import app.database.board as board_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase
from app.api.posts.response_case import PostResponseCase


class PostCreationRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
        },
        auth={api_class.AuthType.Bearer: True, })
    @api_class.RequestBody(
        required_fields={
            'title': {'type': 'string', },
            'body': {'type': 'string', },
        },
        optional_fields={
            'announcement': {'type': 'boolean', },
            'private': {'type': 'boolean', },
            'commentable': {'type': 'boolean', },
        })
    def post(self,
             board_id: int,
             req_header: dict,
             access_token: jwt_module.AccessToken,
             req_body: dict):
        '''
        description: Create new post
        responses:
            - access_token_invalid
            - post_created
            - server_error
        '''
        # Get user access token and check permission
        # Is user admin? Admin can do everything, including writing announcement post
        user_is_superuser: bool = True if access_token.role in ('admin', ) else False

        try:
            board_info: board_module.Board = board_module.Board.query\
                .filter(board_module.Board.deleted == False)\
                .filter(board_module.Board.locked == False)\
                .filter(board_module.Board.uuid == board_id)\
                .first()  # noqa
            if not board_info:
                return PostResponseCase.board_not_found.create_response()

            # Get user data from table using access token
            target_user: user_module.User = user_module.User.query\
                .filter(user_module.User.uuid == access_token.user)\
                .filter(user_module.User.deactivated_at is not None)\
                .filter(user_module.User.locked_at is not None)\
                .first()
            if not target_user:
                return AccountResponseCase.access_token_invalid.create_response()

            new_post = board_module.Post()
            new_post.user_id = access_token.user
            new_post.board_id = board_id
            new_post.title = req_body['title']
            new_post.body = req_body['body']

            new_post.private = bool(req_body.get('private', False))
            new_post.commentable = bool(req_body.get('commentable', True))
            new_post.announcement = bool(req_body.get('announcement', False)) if user_is_superuser\
                else False

            db_module.db.session.add(new_post)
            db_module.db.session.commit()

            return PostResponseCase.post_created.create_response(
                data=new_post.to_dict(True),
                header=(
                    ('ETag', new_post.commit_id),
                    ('Last-Modified', new_post.modified_at),
                ))
        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()
