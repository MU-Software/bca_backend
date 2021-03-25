import datetime
import flask
import flask.views
import sqlalchemy as sql

import app.api as api
import app.common.utils as utils
import app.database as db_module
import app.database.user as user_module
import app.database.jwt as jwt_module
import app.database.board as board_module

import app.common.firebase_notify as firebase_notify

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase
from app.api.posts.response_case import PostResponseCase


def has_post_permission(
        access_token: jwt_module.AccessToken,
        post_obj: board_module.Post,
        action: str) -> bool:
    try:
        # Only those actions are allowed, we must check 'post' when user uploads post.
        if action not in ('get', 'put', 'delete'):
            return False

        # Anyone must not access to deleted post
        if not post_obj or post_obj.locked or post_obj.deleted:
            return False

        # Get user data from table using access token
        if not access_token or access_token.user < 0:
            return False

        target_user: user_module.User = user_module.User.query.filter(
                                            user_module.User.uuid == access_token.user
                                        ).first()
        if not target_user or target_user.deactivated_at or target_user.locked_at:
            return False

        # Is user admin?
        if target_user.role in ('admin', ):
            # Admin can do everything, without modifying.
            return False if action == 'put' else True

        # Is user author of post?
        if post_obj.user_id == target_user.uuid:
            # Even though the user is author, author cannot get permission when some flags are set
            if action == 'get':
                return True
            elif action == 'put' or action == 'delete':
                return post_obj.modifiable
    except Exception:
        pass

    return False


class PostCommentGetRoute(flask.views.MethodView, api.MethodViewMixin):
    # Return post comments
    # This is the only route of this class
    def get(self, post_id: str):
        if not post_id:
            return CommonResponseCase.http_mtd_forbidden.create_response(
                data={'lacks': ['post_id']})
        elif not post_id.isdigit():
            return CommonResponseCase.http_mtd_forbidden.create_response()
        post_id = int(post_id)

        target_post: board_module.Post = None
        try:
            target_post = board_module.Post.query\
                .filter(not board_module.Post.locked)\
                .filter(not board_module.Post.deleted)\
                .filter(board_module.Post.uuid == int(post_id)).first()
        except Exception:
            return CommonResponseCase.db_error.create_response()
        if not target_post:
            return PostResponseCase.post_not_found.create_response()

        user_has_power: bool = False  # This var will be used on comment processing
        access_token: jwt_module.AccessToken = None
        # if target_post.private == False, then response post data
        if target_post.private:
            # Get user access token and check it
            access_token = jwt_module.get_account_data()

            if not access_token:
                if access_token is False:
                    return AccountResponseCase.access_token_expired.create_response()
                return AccountResponseCase.access_token_invalid.create_response()
            else:
                # Check user permission
                user_has_power = has_post_permission(access_token, target_post, 'get')

                if not user_has_power:
                    return PostResponseCase.post_forbidden.create_response()

        response_comments = list()
        comment: board_module.Comment = None
        for comment in target_post.comments:
            if not comment.deleted:  # if comment is not deleted
                is_comment_readable: bool = (not comment.private) or user_has_power
                if not is_comment_readable and access_token:
                    if comment.user_id == access_token.user:
                        is_comment_readable = True

                response_comments.append({
                    'id': comment.id,

                    'created_at': comment.created_at,
                    'modified': comment.created_at == comment.modified_at,
                    'modified_at': comment.modified_at,

                    'private': comment.private,
                    'deleted': False,

                    'user': comment.user.nickname,
                    'user_id': comment.user_id,
                    'is_post_author': target_post.user_id == comment.user_id,

                    'parent': comment.parent_id,
                    'order': comment.order,

                    'body': '' if not is_comment_readable else comment.body
                })
            else:  # if comment is deleted
                response_comments.append({
                    'id': comment.id,

                    'created_at': 0,
                    'modified': True,
                    'modified_at': 0,

                    'private': True,
                    'deleted': True,

                    'user': '',
                    'user_id': 0,
                    'is_post_author': False,

                    'parent': comment.parent_id,
                    'order': comment.order,

                    'body': ''
                })

        return PostResponseCase.post_found.create_response(data={'comments': response_comments})


class PostCommentRoute(flask.views.MethodView, api.MethodViewMixin):
    # Create new comment
    def post(self, post_id: str, comment_id: str):
        if (not post_id) or (not comment_id):
            return CommonResponseCase.http_mtd_forbidden.create_response(
                data={'lacks': ['post_id', 'comment_id']})
        if (not post_id.isdigit()) or (comment_id.lower() != 'new'):
            return CommonResponseCase.http_mtd_forbidden.create_response()
        post_id = int(post_id)
        comment_id = int(comment_id)

        # Get user-written comment data from request
        comment_req = utils.request_body(
            required_fields=['body', ],
            optional_fields=['private', 'parent_id'])
        if type(comment_req) == list:
            return CommonResponseCase.body_required_omitted.create_response(data={'lacks': comment_req})
        elif comment_req is None:
            return CommonResponseCase.body_invalid.create_response()
        elif not comment_req:
            return CommonResponseCase.body_empty.create_response()
        elif type(comment_req) != dict:
            return CommonResponseCase.body_invalid.create_response()

        # Get user access token and check it
        access_token: jwt_module.AccessToken = jwt_module.get_account_data()

        # Check access token on request
        if not access_token:
            if access_token is False:
                return AccountResponseCase.access_token_expired.create_response()
            return AccountResponseCase.access_token_invalid.create_response()

        # Check user permission
        target_user: user_module.User = None
        try:
            # Get user data from table using access token
            if access_token.user < 0:
                return AccountResponseCase.access_token_invalid.create_response()

            target_user = jwt_module.get_account_data()
            if target_user is None:
                return AccountResponseCase.user_not_signed_in.create_response()
            elif not target_user:
                return AccountResponseCase.access_token_invalid.create_response()
        except Exception:
            return PostResponseCase.post_forbidden.create_response()

        # Get target post
        target_post: board_module.Post = None
        try:
            if post_id.user < 0:
                return PostResponseCase.post_not_found.create_response()

            target_post = board_module.Post.query\
                .filter(not board_module.Post.deleted)\
                .filter(board_module.Post.locked)\
                .filter(board_module.Post.uuid == post_id)\
                .first()
        except Exception:
            return CommonResponseCase.db_error.create_response()
        if not target_post:
            return PostResponseCase.post_not_found.create_response()
        if not target_post.commentable:
            return PostResponseCase.post_forbidden.create_response()

        # Calculate comment order
        comment_order: int = 0
        try:
            last_comment_query = board_module.Comment.query\
                .filter(board_module.Comment.post_id == post_id)

            if ('parent_id' in comment_req) and (type(comment_req.get('parent_id')) == int):
                last_comment_query = last_comment_query.filter(
                    board_module.Comment.parent_id == int(comment_req['parent_id']))
            last_comment_query = last_comment_query.order_by(sql.desc(board_module.Comment.order))
            comment_order = last_comment_query.first().order + 1
        except Exception:
            return CommonResponseCase.db_error.create_response()

        try:
            new_comment = board_module.Comment()
            new_comment.user = target_user
            new_comment.post = target_post
            new_comment.body = comment_req['body']
            new_comment.order = comment_order
            new_comment.parent_id = int(comment_req['parent_id']) if 'parent_id' in comment_req else None
            new_comment.private = bool(comment_req.get('private', False))

            db_module.db.session.add(new_comment)
            db_module.db.session.commit()

            # Send notification to related users
            target_user_clients: list[jwt_module.RefreshToken]
            target_user_clients = list(jwt_module.RefreshToken.query
                                       .filter(jwt_module.RefreshToken.user == target_post.user_id)
                                       .filter(jwt_module.RefreshToken.client_token is not None).all())
            if 'parent_id' in comment_req:
                target_user_clients += list(jwt_module.RefreshToken.query
                                            .join(board_module.Comment,
                                                  jwt_module.RefreshToken.user == board_module.Comment.user_id)
                                            .filter(board_module.Comment.uuid == int(comment_req['parent_id']))
                                            .filter(jwt_module.RefreshToken.client_token is not None).all())

            for target_user_client in target_user_clients:
                firebase_notify.firebase_send_notify(
                    title=f'새 {"대" if "parent_id" in comment_req else ""}댓글이 달렸습니다!',
                    body=f'{target_user.nickname}: {new_comment.body}',
                    topic='게시글 알림', target_token=target_user_client.client_token)

            return PostResponseCase.post_created.create_response(data={'id': new_comment.uuid})
        except Exception:
            return CommonResponseCase.db_error.create_response()

    # Modify comment
    def patch(self, post_id: str, comment_id: str):
        if (not post_id) or (not comment_id):
            return CommonResponseCase.http_mtd_forbidden.create_response(
                data={'lacks': ['post_id', 'comment_id']})
        if (not post_id.isdigit()) or (not comment_id.isdigit()):
            return CommonResponseCase.http_mtd_forbidden.create_response()
        post_id = int(post_id)
        comment_id = int(comment_id)

        comment_req = utils.request_body(
            required_fields=[],
            optional_fields=['body', 'private'])
        if type(comment_req) == list:
            return CommonResponseCase.body_required_omitted.create_response(data={'lacks': comment_req})
        elif comment_req is None:
            return CommonResponseCase.body_invalid.create_response()
        elif not comment_req:
            return CommonResponseCase.body_empty.create_response()
        elif type(comment_req) != dict:
            return CommonResponseCase.body_invalid.create_response()

        target_comment: board_module.Comment = None
        try:
            target_comment = board_module.Comment.query\
                .filter(not board_module.Comment.deleted)\
                .filter(board_module.Comment.post_id == post_id)\
                .filter(board_module.Comment.uuid == comment_id)\
                .first()
        except Exception:
            return CommonResponseCase.db_error.create_response()
        if not target_comment:
            return PostResponseCase.post_not_found.create_response()
        if not target_comment.modifiable:
            return PostResponseCase.post_forbidden.create_response()

        # Check requested user is comment's author
        access_token: jwt_module.AccessToken = jwt_module.get_account_data()

        if not access_token:
            if access_token is False:
                return AccountResponseCase.access_token_expired.create_response()
            return AccountResponseCase.access_token_invalid.create_response()

        # Is req_user author? (author cannot modify comment when post is not modifiable)
        if (target_comment.user_id != access_token.user) or (not target_comment.modifiable):
            return PostResponseCase.post_forbidden.create_response()

        try:
            # Modify post using request body
            for req_key, req_value in comment_req.items():
                setattr(target_comment, req_key, req_value)
            db_module.db.session.commit()

            return PostResponseCase.post_modified.create_response()
        except Exception:
            return CommonResponseCase.db_error.create_response()

    # Delete comment
    def delete(self, post_id: str, comment_id: str):
        # Check requested user has permission to delete,
        # is req_user manager or a comment author? (author cannot delete post when post is not deletable)
        if (not post_id) or (not comment_id):
            return CommonResponseCase.http_mtd_forbidden.create_response(
                data={'lacks': ['post_id', 'comment_id']})
        if (not post_id.isdigit()) or (not comment_id.isdigit()):
            return CommonResponseCase.http_mtd_forbidden.create_response()
        post_id = int(post_id)
        comment_id = int(comment_id)

        target_comment: board_module.Comment = None
        try:
            target_comment = board_module.Comment.query\
                .filter(not board_module.Comment.deleted)\
                .filter(board_module.Comment.post_id == post_id)\
                .filter(board_module.Comment.uuid == comment_id)\
                .first()
        except Exception:
            return CommonResponseCase.db_error.create_response()
        if not target_comment:
            return PostResponseCase.post_not_found.create_response()

        # Get user access token and check it
        access_token: jwt_module.AccessToken = jwt_module.get_account_data()

        if not access_token:
            if access_token is False:
                return AccountResponseCase.access_token_expired.create_response()
            return AccountResponseCase.access_token_invalid.create_response()

        try:
            target_user: user_module.User = user_module.User.query\
                .filter(user_module.User.uuid == access_token.user)\
                .filter(user_module.User.deactivated_at is None)\
                .filter(user_module.User.locked_at is None)\
                .first()
        except Exception:
            return CommonResponseCase.db_error.create_response()
        if not target_user:
            return AccountResponseCase.user_not_found.create_response()

        # Check user permission
        if target_user.role in ['admin', ]:  # if user == 'admin', then user can delete comment
            pass
        if target_user.uuid != target_comment.user_id:
            # if user == author, then user can delete comment when comment is deletable
            if not target_comment.deletable:
                return PostResponseCase.post_forbidden.create_response()
        else:
            return PostResponseCase.post_forbidden.create_response()

        try:
            target_comment.deleted = True
            target_comment.deleted_at = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)
            target_comment.deleted_by_id = access_token.user
            db_module.db.session.commit()
            return PostResponseCase.post_deleted.create_response(data={'id': target_comment.uuid})
        except Exception:
            return CommonResponseCase.db_error.create_response()
