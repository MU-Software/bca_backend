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

    # Unauthorized means there's no account information on header,
    # while Forbidden means the user don't have permission on request action
    post_unauthorized = api.Response(
        code=401, success=False,
        public_sub_code='post.unauthorized')
    post_forbidden = api.Response(
        code=401, success=False,
        public_sub_code='post.forbidden')

    post_created = api.Response(
        code=201, success=True,
        public_sub_code='post.created',
        data={'id': 0})
    post_modified = api.Response(
        code=201, success=True,
        public_sub_code='post.modified',
        data={'id': 0})
    post_deleted = api.Response(
        code=201, success=True,
        public_sub_code='post.deleted',
        data={'id': 0})
