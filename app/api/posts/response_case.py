import app.api.helper_class as api_class


class PostResponseCase(api_class.ResponseCaseCollector):
    board_not_found = api_class.Response(
        description='Board you requested not found.',
        code=404, success=True,
        public_sub_code='board.not_found')

    post_found = api_class.Response(
        description='Post you requested found.',
        code=200, success=True,
        public_sub_code='post.result')
    post_not_found = api_class.Response(
        description='Post you requested couldn\'t be found.',
        code=404, success=False,
        public_sub_code='post.not_found')
    post_list = api_class.Response(
        description='This is a list of posts.',
        code=200, success=True,
        public_sub_code='post.list')

    post_forbidden = api_class.Response(
        description='You don\'t have permissions to do such thing on this post.',
        code=401, success=False,
        public_sub_code='post.forbidden')
    post_prediction_failed = api_class.Response(
        description='Post has been modified by someone, and you tried to modify this post with old version.',
        code=412, success=False,
        public_sub_code='post.prediction_failed')

    post_created = api_class.Response(
        description='We successfully created a post.',
        code=201, success=True,
        public_sub_code='post.created',
        data={'id': 0})
    post_modified = api_class.Response(
        description='We successfully modified a post.',
        code=201, success=True,
        public_sub_code='post.modified',
        data={'id': 0})
    post_deleted = api_class.Response(
        description='We successfully deleted a post.',
        code=204, success=True,
        public_sub_code='post.deleted',
        data={'id': 0})
