import flask
import flask.views
import jwt
import typing

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

            # We need to show icon when post is deleted or private
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
        })

    # Create post
    def post(self, post_id: str):
        if not post_id or post_id.lower() != 'new':
            return CommonResponseCase.http_mtd_forbidden.create_response()

        try:
            post_req = flask.request.get_json(force=True)
            post_req = {k: v for k, v in post_req.items() if v}

            required_fields = ['title', 'body']
            if (not all([z in post_req.keys() for z in required_fields])) or (not all(list(post_req.values()))):
                return CommonResponseCase.body_required_omitted.create_response(data={'lacks': []})
        except Exception:
            return CommonResponseCase.body_invalid.create_response()

        # Get user account from access token
        # Check if user can create a post
        new_post = board_module.Post()
        new_post.title = ''
        new_post.body = ''
        new_post.user = None
        db_module.db.session.add(new_post)
        db_module.db.session.commit()

        return PostResponseCase.post_created.create_response(data={'id': 0})

