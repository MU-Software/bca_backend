import flask
import flask.views
import app.api as api

import app.database as db_module
import app.database.user as user_module
import app.database.jwt as jwt_module
import app.database.board as board_module

from app.api.response_case import CommonResponseCase
from app.api.posts.response_case import PostResponseCase


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

        # TODO: Check user read permission
        user_has_power = False

        if not target_post or target_post.deleted:
            return PostResponseCase.post_not_found.create_response()
        if not target_post.readable:
            return PostResponseCase.post_forbidden.create_response()
        if target_post.private:
            # TODO: can read post if target_post.user == access_jwt_user or access_jwt_user.role == 'manager'
            return PostResponseCase.post_forbidden.create_response()

        response_comments = list()
        comment: board_module.Comment = None
        for comment in target_post.comments:
            is_comment_readable: bool = not (comment.deleted) and \
                                        (
                                            (not user_has_power) and
                                            (target_post.user_id != comment.user_id)
                                        )
            response_comments.append({
                'id': comment.id,

                'created_at': comment.created_at,
                'modified': comment.created_at == comment.modified_at,
                'modified_at': comment.modified_at,

                'deleted': comment.deleted,
                'private': comment.private,

                'user': comment.user.nickname,
                'user_id': comment.user_id,
                'is_author': target_post.user_id == comment.user_id,

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

