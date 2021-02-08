import flask
import flask.views
import math
import sqlalchemy as sql

import app.common.utils as utils
import app.database.jwt as jwt_module
import app.database.board as board_module

from app.api.response_case import CommonResponseCase
from app.api.account.response_case import AccountResponseCase
from app.api.posts.response_case import PostResponseCase


class PostListRoute(flask.views.MethodView):
    def get(self):
        user_is_admin: bool = False
        target_user_id: int = 0
        access_token = jwt_module.get_account_data()

        # Check access token on request
        if access_token is False:
            return AccountResponseCase.access_token_expired.create_response()
        if access_token:
            target_user_id = access_token.user

        # Show all announcement posts on top of each page
        # TODO: Make post_list_query to query announcement too,
        #       so that querying posts can be done in one time instead of querying multiple times
        post_announcements: list[board_module.Post] = []
        try:
            post_announcements: list[board_module.Post] = board_module.Post.query\
                .filter(not board_module.Post.deleted)\
                .filter(not board_module.Post.locked)\
                .filter(board_module.Post.announcement)\
                .all()
            post_announcements = post_announcements if post_announcements else []
        except Exception:
            return CommonResponseCase.db_error.create_response()

        # Query normal posts
        post_list_query = board_module.Post.query\
            .filter(not board_module.Post.deleted)\
            .filter(not board_module.Post.locked)  # Query builder
        if not user_is_admin:  # Show all private posts if user.role == admin, else then filter it
            # Exclude private post except if user is private posts' author
            post_list_query = post_list_query.filter(
                sql.or_(
                    # Show post if post is not private, or post's author is user
                    not board_module.Post.private,
                    board_module.Post.user_id == target_user_id))
        post_list_query = post_list_query.order_by(sql.desc(board_module.Post.created_at))

        # TODO: Add more list filtering option, such as tagging

        # Range-query posts(Paging ability)
        try:
            req_post_per_page: int = utils.safe_int(flask.request.get('count-per-page', 0))
            req_post_per_page = 25 if (not req_post_per_page) or (req_post_per_page > 100) else req_post_per_page
            post_list_query = post_list_query.limit(req_post_per_page)

            post_count: int = post_list_query.count()
            page_count = int(math.ceil(post_count / req_post_per_page))

            req_page_number: int = 0
            if flask.request.has('page'):
                req_page_number: int = utils.safe_int(flask.request.get('page', 0))
                if page_count < req_page_number:
                    req_page_number = page_count

                post_list_query = post_list_query.offset(req_page_number * req_post_per_page)

            elif flask.request.has('last-offset'):
                req_last_offset: int = utils.safe_int(flask.request.get('last-offset', 0))
                post_list_query = post_list_query.filter(board_module.Post.uuid < req_last_offset)

            else:
                post_list_query = post_list_query.offset(0)

            result_post_list: list = list()
            post_list: list[board_module.Post] = post_list_query.all()
            for post in post_announcements + post_list:
                # TODO: Add like and comment counts
                result_post_list.append({
                    'announcement': post.announcement,
                    'post_id': post.uuid,
                    'title': post.title,

                    'user': post.user.nickname,
                    'user_id': post.user_id,
                    'is_post_author': post.user_id == target_user_id,

                    'created_at': post.created_at,
                    'modified': post.created_at == post.modified_at,
                    'modified_at': post.modified_at,
                })
        except Exception:
            return CommonResponseCase.db_error.create_response()

        return PostResponseCase.post_found.create_response(data={
            'total_page': page_count,
            'page': req_page_number,
            'total_post': post_count,
            'posts': result_post_list
        })
