import flask
import flask.views

import app.api as api
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.board as board_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase
from app.api.posts.response_case import PostResponseCase


class PostLikeRoute(flask.views.MethodView, api.MethodViewMixin):
    # Return who liked this post
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
                .filter(board_module.Post.uuid == post_id).first()
        except Exception:
            return CommonResponseCase.db_error.create_response()
        if not target_post:
            return PostResponseCase.post_not_found.create_response()

        like_result: list = list()
        likes: board_module.PostLike = None
        for likes in target_post.liked_by:
            if (not likes.user.locked_at) and (not likes.user.deactivated_at):
                like_result.append({
                    'user_id': likes.user_id,
                    'nickname': likes.user.nickname,
                })

        return PostResponseCase.post_found.create_response(data={'liked_by': like_result})

    # Mark 'user likes this post'
    def post(self, post_id: str):
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
                .filter(board_module.Post.uuid == post_id).first()
        except Exception:
            return CommonResponseCase.db_error.create_response()
        if not target_post:
            return PostResponseCase.post_not_found.create_response()

        # Get user access token and get user id
        access_token: jwt_module.AccessToken = jwt_module.get_account_data()

        # Check access token on request
        if not access_token:
            if access_token is False:
                return AccountResponseCase.access_token_expired.create_response()
            return AccountResponseCase.user_not_signed_in.create_response()

        if target_post.user_id == access_token.user:
            # User cannot like own posts
            return PostResponseCase.post_forbidden.create_response()

        try:
            new_like_relation = board_module.PostLike()
            new_like_relation.user_id = access_token.user
            new_like_relation.post = target_post

            db_module.db.session.add(new_like_relation)
            db_module.db.session.commit()

            return PostResponseCase.post_created.create_response()
        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()

    # Now, User doesn't like this post
    def delete(self, post_id: str):
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
                .filter(board_module.Post.uuid == post_id).first()
        except Exception:
            return CommonResponseCase.db_error.create_response()
        if not target_post:
            return PostResponseCase.post_not_found.create_response()

        # Get user access token and get user id
        access_token: jwt_module.AccessToken = jwt_module.get_account_data()

        # Check access token on request
        if not access_token:
            if access_token is False:
                return AccountResponseCase.access_token_expired.create_response()
            return AccountResponseCase.user_not_signed_in.create_response()

        # Now, we need to query PostLike relation table
        target_like_rel: board_module.PostLike = None
        try:
            target_like_rel = board_module.PostLike.query\
                                    .filter(board_module.PostLike.post_id == post_id)\
                                    .filter(board_module.PostLike.user_id == access_token.user)\
                                    .first()
            if not target_like_rel:
                return PostResponseCase.post_not_found.create_response()

            db_module.db.session.delete(target_like_rel)
            db_module.db.session.commit()
            return PostResponseCase.post_deleted.create_response()
        except Exception:
            return CommonResponseCase.db_error.create_response()
