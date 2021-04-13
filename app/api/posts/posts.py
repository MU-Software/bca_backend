import datetime
import flask
import flask.views
import typing

import app.api.helper_class as api_class
import app.common.utils as utils
import app.database as db_module
import app.database.user as user_module
import app.database.jwt as jwt_module
import app.database.board as board_module

from app.api.response_case import CommonResponseCase
from app.api.posts.response_case import PostResponseCase


def has_post_permission(
        access_token: jwt_module.AccessToken,
        post_obj: board_module.Post,
        action: str) -> bool:
    try:
        # Only those actions are allowed, we must check separately when user uploads post.
        if action not in ('get', 'put', 'delete'):
            return False

        # Anyone must not access to deleted post
        if not post_obj or post_obj.locked or post_obj.deleted:
            return False

        # Get user data from table using access token
        if not access_token or access_token.user < 0:
            return False

        target_user: user_module.User = user_module.User.query\
            .filter(user_module.User.uuid == access_token.user)\
            .filter(user_module.User.locked_at is not None)\
            .filter(user_module.User.deactivated_at is not None)\
            .first()
        if not target_user:
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


class PostRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={},
        optional_fields={
            'X-Csrf-Token': {'type': 'string', },
        },
        auth={api_class.AuthType.Bearer: False, })
    def get(self,
            board_id: int,
            post_id: int,
            req_header: dict,
            access_token: typing.Optional[jwt_module.AccessToken]):
        '''
        description: Return post and comments
        responses:
            - post_found
            - post_not_found
            - post_forbidden
            - db_error
            - server_error
        '''
        try:
            target_post: board_module.Post = board_module.Post.query\
                .filter(board_module.Post.locked == False)\
                .filter(board_module.Post.deleted == False)\
                .filter(board_module.Post.board_id == board_id)\
                .filter(board_module.Post.uuid == post_id).first()  # noqa
            if not target_post:
                return PostResponseCase.post_not_found.create_response()
        except Exception:
            return CommonResponseCase.db_error.create_response()

        # if target_post.private == False, then response post data
        if target_post.private:
            # if post is private, then only admin and post owner can see this.
            if not access_token or\
               access_token.role not in ('admin', ) or\
               access_token.user == target_post.user_id:
                return PostResponseCase.post_forbidden.create_response()

        response_comments = list()
        try:
            comment: board_module.Comment = board_module.Comment.query\
                .filter(board_module.Comment.post_id == target_post.uuid)\
                .filter(board_module.Comment.deleted == False)\
                .all()  # noqa
            for comment in target_post.comments:
                is_comment_readable: bool = not comment.private
                if not is_comment_readable and access_token:
                    if access_token.role in ('admin', ) or access_token.user == target_post.user_id:
                        is_comment_readable = True

                comment_data = comment.to_dict(is_comment_readable)
                comment_data['is_post_author'] = target_post.user_id == comment_data['user_id']
                response_comments.append(comment.to_dict(is_comment_readable))
        except Exception:
            # Just ignore comments when error occurs
            pass

        post_data = target_post.to_dict(True)
        post_data['comments'] = response_comments
        return PostResponseCase.post_found.create_response(
            data=post_data,
            header=(
                ('ETag', target_post.commit_id),
                ('Last-Modified', target_post.modified_at),
            ))

    # # Modify post
    # def patch(self, post_id: int):
    #     post_req = utils.request_body(
    #         required_fields=[],
    #         optional_fields=[
    #             'title', 'body',
    #             'announcement', 'private', 'commentable'])
    #     if type(post_req) == list:
    #         return CommonResponseCase.body_required_omitted.create_response(data={'lacks': post_req})
    #     elif post_req is None:
    #         return CommonResponseCase.body_invalid.create_response()
    #     elif not post_req:
    #         return CommonResponseCase.body_empty.create_response()
    #     elif type(post_req) != dict:
    #         return CommonResponseCase.body_invalid.create_response()

    #     target_post: board_module.Post = None
    #     try:
    #         target_post = board_module.Post.query\
    #             .filter(board_module.Post.locked == False)\
    #             .filter(board_module.Post.deleted == False)\
    #             .filter(board_module.Post.uuid == int(post_id)).first()
    #     except Exception:
    #         return CommonResponseCase.db_error.create_response()
    #     if not target_post:
    #         return PostResponseCase.post_not_found.create_response()

    #     # Check requested user is author
    #     access_token: jwt_module.AccessToken = jwt_module.get_account_data()

    #     if not access_token:
    #         if access_token is False:
    #             return AccountResponseCase.access_token_expired.create_response()
    #         return AccountResponseCase.access_token_invalid.create_response()

    #     # Check Etag
    #     if req_etag := flask.request.headers.get('If-Match', False):
    #         if req_etag != target_post.commit_id:
    #             return PostResponseCase.post_prediction_failed.create_response()
    #     elif req_modified_at := flask.request.headers.get('If-Unmodified-Since', False):
    #         try:
    #             req_modified_at = datetime.datetime.strptime(req_modified_at, '%a, %d %b %Y %H:%M:%S GMT')
    #             if target_post.modified_at > req_modified_at:
    #                 return PostResponseCase.post_prediction_failed.create_response()
    #         except Exception:
    #             return CommonResponseCase.header_invalid.create_response()
    #     else:
    #         return CommonResponseCase.header_required_omitted.create_response(data={'lacks': ['ETag', ]})

    #     # Is req_user author? (author cannot modify post when post is not modifiable)
    #     if (target_post.user_id != access_token.user) or (not target_post.modifiable):
    #         return PostResponseCase.post_forbidden.create_response()

    #     try:
    #         # Modify post using request body
    #         for req_key, req_value in post_req.items():
    #             setattr(target_post, req_key, req_value)
    #         db_module.db.session.commit()

    #         return PostResponseCase.post_modified.create_response()
    #     except Exception:
    #         return CommonResponseCase.db_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
        },
        optional_fields={
            'If-Match': {'type': 'string', },
            'If-Unmodified-Since': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self,
               board_id: int,
               post_id: int,
               req_header: dict,
               access_token: jwt_module.AccessToken):
        '''
        description: Delete post
        responses:
            - post_deleted
            - post_not_found
            - post_forbidden
            - post_prediction_failed
            - header_invalid
            - header_required_omitted
            - db_error
            - server_error
        '''
        # Check requested user has permission to delete,
        # Is req_user manager or author? (author cannot delete post when post is not deletable)
        target_post: board_module.Post = None
        try:
            target_post = board_module.Post.query\
                .filter(board_module.Post.locked == False)\
                .filter(board_module.Post.deleted == False)\
                .filter(board_module.Post.board_id == board_id)\
                .filter(board_module.Post.uuid == int(post_id)).first()  # noqa
        except Exception:
            return CommonResponseCase.db_error.create_response()
        if not target_post:
            return PostResponseCase.post_not_found.create_response()

        # Check user permission
        if not has_post_permission(access_token, target_post, 'delete'):
            return PostResponseCase.post_forbidden.create_response()

        # Check Etag
        if req_etag := req_header.get('If-Match', False):
            if req_etag != target_post.commit_id:
                return PostResponseCase.post_prediction_failed.create_response()
        elif req_modified_at := req_header.get('If-Unmodified-Since', False):
            try:
                req_modified_at = datetime.datetime.strptime(req_modified_at, '%a, %d %b %Y %H:%M:%S GMT')
                if target_post.modified_at > req_modified_at:
                    return PostResponseCase.post_prediction_failed.create_response()
            except Exception:
                return CommonResponseCase.header_invalid.create_response()
        else:
            return CommonResponseCase.header_required_omitted.create_response(
                data={
                    'lacks': [
                        'If-Match',
                        'If-Unmodified-Since']})

        try:
            target_post.deleted = True
            target_post.deleted_at = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)
            target_post.deleted_by_id = access_token.user
            db_module.db.session.commit()

            return PostResponseCase.post_deleted.create_response(
                data={'id': target_post.uuid}
            )
        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()
