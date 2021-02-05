import app.api as api


class PostResponseCase(api.ResponseCaseCollector):
    post_found = api.Response(
        code=200, success=True,
        public_sub_code='post.result')
    post_not_found = api.Response(
        code=404, success=False,
        public_sub_code='post.not_found')
    post_list = api.Response(
        code=200, success=True,
        public_sub_code='post.list')

    post_forbidden = api.Response(
        code=401, success=False,
        public_sub_code='post.forbidden')
    post_prediction_failed = api.Response(
        code=412, success=False,
        public_sub_code='post.prediction_failed')

    post_created = api.Response(
        code=201, success=True,
        public_sub_code='post.created',
        data={'id': 0})
    post_modified = api.Response(
        code=201, success=True,
        public_sub_code='post.modified',
        data={'id': 0})
    post_deleted = api.Response(
        code=204, success=True,
        public_sub_code='post.deleted',
        data={'id': 0})
