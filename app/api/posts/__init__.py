import app.api.posts.post_paging as post_paging
import app.api.posts.posts as posts

resource_route = {
    '/posts/': post_paging.PostListRoute,
    '/posts/<string:post_id>': posts.PostRoute,
}
