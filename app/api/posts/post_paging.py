import flask
import flask.views
import math
import sqlalchemy as sql
import typing

import app.api.helper_class as api_class
import app.common.utils as utils
import app.database.jwt as jwt_module
import app.database.board as board_module

from app.api.response_case import CommonResponseCase
from app.api.posts.response_case import PostResponseCase


class PostListRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={},
        optional_fields={
            'X-Csrf-Token': {'type': 'string', },
        },
        auth={api_class.AuthType.Bearer: False, })
    @api_class.RequestQuery(
        required_fields={},
        optional_fields={
            'page': {'type': 'integer'},
            'count-per-page': {'type': 'integer'},
            'last-offset': {'type': 'integer'}, })
    def get(self,
            board_id: int,
            req_header: dict,
            access_token: typing.Optional[jwt_module.AccessToken],
            req_query: dict):
        '''
        description: Show post list on board (with announcement)
        responses:
            - post_found
            - db_error
        '''
        # TODO: Make post_list_query to query announcement too,
        #       so that querying posts can be done in one time instead of querying multiple times
        try:
            try:
                board_info: board_module.Board = board_module.Board.query\
                    .filter(board_module.Board.deleted == False)\
                    .filter(board_module.Board.locked == False)\
                    .filter(board_module.Board.uuid == board_id)\
                    .first()  # noqa
                if not board_info:
                    return PostResponseCase.board_not_found.create_response()
            except Exception as err:
                print(utils.get_traceback_msg(err))
                return CommonResponseCase.db_error.create_response()

            post_announcements: list[board_module.Post] = board_module.Post.query\
                .filter(board_module.Post.deleted == False)\
                .filter(board_module.Post.locked == False)\
                .filter(board_module.Post.board_id == board_id)\
                .filter(board_module.Post.announcement)\
                .all() or [] # noqa

            # Query normal posts
            post_list_query = board_module.Post.query\
                .filter(board_module.Post.deleted == False)\
                .filter(board_module.Post.locked == False)\
                .filter(board_module.Post.board_id == board_id)\
                .filter(board_module.Post.announcement == False)  # Query builder  # noqa

            # Show all private posts if user.role == admin
            if access_token:
                # admin can see all private posts
                # signed-in user can't see private posts, except her own posts
                # else: they can't see any of private posts
                if access_token.role not in ('admin', ):
                    # Exclude private post except if user is private posts' author
                    post_list_query = post_list_query\
                        .filter(sql.or_(
                            board_module.Post.private is False,
                            board_module.Post.user_id == access_token.user))
            else:
                post_list_query = post_list_query.filter(board_module.Post.private == False)  # noqa

            # TODO: Add more list filtering option, such as tagging

            # Filtering finish, now order and limit
            post_list_query = post_list_query.order_by(sql.desc(board_module.Post.created_at))

            # Range-query posts(Paging ability
            req_post_per_page: int = utils.safe_int(flask.request.args.get('count-per-page', 0))
            req_post_per_page = 25 if (not req_post_per_page) or (req_post_per_page > 100) else req_post_per_page
            post_list_query = post_list_query.limit(req_post_per_page)

            post_count: int = post_list_query.count()
            page_count = int(math.ceil(post_count / req_post_per_page))

            req_page_number: int = 0
            if 'page' in req_query:
                req_page_number: int = utils.safe_int(req_query.get('page', 0))
                if page_count < req_page_number:
                    req_page_number = page_count

                post_list_query = post_list_query.offset(req_page_number * req_post_per_page)

            elif 'last-offset' in req_query:
                req_last_offset: int = utils.safe_int(req_query.get('last-offset', 0))
                post_list_query = post_list_query.filter(board_module.Post.uuid < req_last_offset)

            else:
                post_list_query = post_list_query.offset(0)

            result_post_list: list = list()
            post_list: list[board_module.Post] = post_list_query.all() or []
            for post in post_announcements + post_list:
                # TODO: Add like and comment counts
                target_fields: list[str] = [
                    'announcement', 'post_id', 'title',
                    'user', 'user_id', 'created_at', 'modified', 'modified_at']
                post_data = {k: v for k, v in post.to_dict(True).items() if k in target_fields}
                post_data['is_post_author'] = False if not access_token else post.user_id == access_token.user
                result_post_list.append(post_data)

            return PostResponseCase.post_found.create_response(data={
                'board_name': board_info.name,
                'board_description': board_info.description,
                'board_type': board_info.board_type,
                'board_created_at': board_info.created_at,

                'is_board_locked': board_info.locked,
                'is_board_commentable': board_info.commentable,
                'is_board_readable': board_info.readable,
                'is_board_private': board_info.private,

                'is_user_authed': access_token is not None,

                'total_page': page_count,
                'page': req_page_number,
                'total_post': post_count,
                'posts': result_post_list
            })

        except Exception as err:
            print(utils.get_traceback_msg(err))
            return CommonResponseCase.db_error.create_response()
