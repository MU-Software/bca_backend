import flask
import flask.views
import jwt
import typing

import app.common.utils as utils
import app.database as db_module
import app.database.user as user_module
import app.database.jwt as jwt_module
import app.database.board as board_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase
from app.api.posts.response_case import PostResponseCase


def get_account_data() -> typing.Union[None, bool, jwt_module.AccessToken]:
    '''
    return case:
        if None: Token not available
        if False: Token must be re-issued
        else: Token Object
    '''
    try:
        access_token_cookie = flask.request.cookies.get('access_token', '')
        if not access_token_cookie:
            return None

        try:
            access_token = jwt_module.AccessToken.from_token(
                access_token_cookie,
                flask.current_app.config.get('SECRET_KEY'))
        except jwt.exceptions.ExpiredSignatureError:
            return False
        except jwt.exceptions.InvalidTokenError as err:
            if err.message == 'This token was revoked':
                return False
            return None
        except Exception:
            return None
        if not access_token:
            return None

        return access_token
    except Exception:
        return None


def has_post_permission(
        access_token: jwt_module.AccessToken,
        post_obj: board_module.Post,
        action: str) -> bool:
    try:
        # Only those actions are allowed, we must check 'post' when user uploads post.
        if action not in ('get', 'put', 'delete'):
            return False

        # Anyone must not access to deleted post
        if not post_obj or post_obj.deleted:
            return False

        # Get user data from table using access token
        if not access_token or access_token.user < 0:
            return False

        target_user: user_module.User = user_module.User.query.filter(
                                            user_module.User.uuid == access_token.user
                                        ).first()
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
                return post_obj.readable
            elif action == 'put' or action == 'delete':
                return post_obj.modifiable
    except Exception:
        pass

    return False


class PostRoute(flask.views.MethodView):
    # Return post content & comments
    def get(self, post_id: str):
        if not post_id:
            return CommonResponseCase.http_mtd_forbidden.create_response(
                data={'lacks': ['post_id']})
        if post_id.lower() == 'new' or not post_id.isdigit():
            return CommonResponseCase.http_mtd_forbidden.create_response()

        target_post: board_module.Post = None
        try:
            target_post = board_module.Post.query.filter(
                board_module.Post.uuid == int(post_id)).first()
        except Exception:
            return CommonResponseCase.db_error.create_response()
        if not target_post or target_post.deleted:
            return PostResponseCase.post_not_found.create_response()

        user_has_power: bool = False  # This var will be used on comment processing
        access_token: jwt_module.AccessToken = None
        # if target_post.private == False and target_post.readable == True, then response post data
        if (target_post.private) or (not target_post.readable):
            # Get user access token and check it
            access_token = get_account_data()

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
            if not comment.deleted:
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

                    'user': comment.user.nickname,
                    'user_id': comment.user_id,
                    'is_post_author': target_post.user_id == comment.user_id,

                    'body': '' if not is_comment_readable else comment.body
                })

        PostResponseCase.post_found.create_response(data={
            'id': post_id,

            'created_at': target_post.created_at,
            'modified': target_post.created_at == target_post.modified_at,
            'modified_at': target_post.modified_at,

            # We need to show icon when post is announcement, deleted or private
            'announcement': target_post.announcement,
            'deleted': target_post.deleted,
            'private': target_post.private,

            # We need to send author's nickname, profile, and author's UUID,
            # uuid is used when frontend user clicks author nick and go to author's profile page
            'user': target_post.user.nickname,
            'user_id': target_post.user_id,

            # Post data
            'title': target_post.title,
            'body': target_post.body,

            # Comments must be filtered
            'comments': response_comments,
        }, header=(
            ('ETag', target_post.commit_id),
            ('Last-Modified', target_post.modified_at),
        ))

    # Create new post
    def post(self, post_id: str):
        if not post_id or post_id.lower() != 'new':
            return CommonResponseCase.http_mtd_forbidden.create_response()

        # Get user access token and check it
        user_is_superuser: bool = False
        access_token: jwt_module.AccessToken = get_account_data()

        # Check access token on request
        if not access_token:
            if access_token is False:
                return AccountResponseCase.access_token_expired.create_response()
            return AccountResponseCase.access_token_invalid.create_response()

        # Check user permission
        try:
            # Get user data from table using access token
            if access_token.user < 0:
                return AccountResponseCase.access_token_invalid.create_response()

            target_user: user_module.User = user_module.User.query.filter(
                                                user_module.User.uuid == access_token.user
                                            ).first()
            if not target_user:
                return AccountResponseCase.access_token_invalid.create_response()

            # Is user admin?
            if target_user.role in ('admin', ):
                # Admin can do everything, including writing announcement post
                user_is_superuser = True
            # Is user on normal state so that user is not deactivated and locked?
            if target_user.deactivated_at or target_user.locked_at:
                return AccountResponseCase.refresh_token_invalid.create_response()

        except Exception:
            return PostResponseCase.post_forbidden.create_response()

        # Get user-written post data from request
        post_req = utils.request_body(
            required_fields=['title', 'body'],
            optional_fields=['announcement', 'private', 'commentable'])
        if not post_req:
            return CommonResponseCase.body_invalid.create_response()
        if type(post_req) == list:
            return CommonResponseCase.body_required_omitted.create_response(data={'lacks': post_req})

        try:
            new_post = board_module.Post()
            new_post.user = target_user
            new_post.title = post_req['title']
            new_post.body = post_req['body']

            new_post.private = bool(post_req.get('private', False))
            new_post.commentable = bool(post_req.get('commentable', True))

            if user_is_superuser:
                new_post.announcement = bool(post_req.get('announcement', False))
            else:
                new_post.announcement = False

            db_module.db.session.add(new_post)
            db_module.db.session.commit()

            return PostResponseCase.post_created.create_response(
                data={
                    'id': new_post.uuid
                }, header=(
                    ('ETag', new_post.commit_id),
                    ('Last-Modified', new_post.modified_at),
                ))
        except Exception:
            return CommonResponseCase.server_error.create_response()

    # Modify post
    def patch(self, post_id: str):
        if not post_id:
            return CommonResponseCase.http_mtd_forbidden.create_response(
                data={'lacks': ['post_id']})
        if not post_id.isdigit():
            return CommonResponseCase.http_mtd_forbidden.create_response()

        post_req = utils.request_body(
            required_fields=[],
            optional_fields=[
                'title', 'body',
                'announcement', 'private', 'commentable'])
        if not post_req:
            return CommonResponseCase.body_invalid.create_response()
        if type(post_req) == list:
            return CommonResponseCase.body_required_omitted.create_response(data={'lacks': post_req})

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

        # Check requested user is author
        access_token: jwt_module.AccessToken = get_account_data()

        if not access_token:
            if access_token is False:
                return AccountResponseCase.access_token_expired.create_response()
            return AccountResponseCase.access_token_invalid.create_response()

        # Check Etag
        if req_etag := flask.request.headers.get('If-Match', False):
            if req_etag != target_post.commit_id:
                return PostResponseCase.post_prediction_failed.create_response()
        elif req_modified_at := flask.request.headers.get('If-Unmodified-Since', False):
            try:
                req_modified_at = datetime.datetime.strptime(req_modified_at, '%a, %d %b %Y %H:%M:%S GMT')
                if target_post.modified_at > req_modified_at:
                    return PostResponseCase.post_prediction_failed.create_response()
            except Exception:
                return CommonResponseCase.header_invalid.create_response()
        else:
            return CommonResponseCase.header_required_omitted.create_response(data={'lacks': ['ETag', ]})

        # Is req_user author? (author cannot modify post when post is not modifiable)
        if (target_post.user_id != access_token.user) or (not target_post.modifiable):
            return PostResponseCase.post_forbidden.create_response()

        # Modify post using request body
        for req_key, req_value in post_req.items():
            setattr(target_post, req_key, req_value)
        db_module.db.session.commit()

        return PostResponseCase.post_modified.create_response()

    # Delete post
    def delete(self, post_id: str):
        # Check requested user has permission to delete,
        # is req_user manager or author? (author cannot delete post when post is not deletable)
        if not post_id:
            return CommonResponseCase.http_mtd_forbidden.create_response(
                data={'lacks': ['post_id']})
        if not post_id.isdigit():
            return CommonResponseCase.http_mtd_forbidden.create_response()

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

        # Get user access token and check it
        access_token: jwt_module.AccessToken = get_account_data()

        if not access_token:
            if access_token is False:
                return AccountResponseCase.access_token_expired.create_response()
            return AccountResponseCase.access_token_invalid.create_response()

        # Check user permission
        if not has_post_permission(access_token, target_post, 'delete'):
            return PostResponseCase.post_forbidden.create_response()

        try:
            target_post.deleted = True
            target_post.deleted_at = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)
            db_module.db.session.commit()
            return PostResponseCase.post_deleted.create_response(
                data={'id': target_post.uuid}
            )
        except Exception:
            return CommonResponseCase.server_error.create_response()
