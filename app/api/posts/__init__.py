import app.api.posts.post_paging as post_paging
import app.api.posts.posts as posts
import app.api.posts.post_create as post_create
import app.api.posts.post_favorite as post_favorite
import app.api.posts.post_like as post_like
import app.api.posts.post_comment as post_comment

resource_route = {
    '/boards/<int:board_id>/': post_paging.PostListRoute,
    '/boards/<int:board_id>/posts/new': post_create.PostCreationRoute,
    '/boards/<int:board_id>/posts/<int:post_id>': posts.PostRoute,
    # '/posts/<string:post_id>/comments': post_comment.PostCommentGetRoute,
    # '/posts/<string:post_id>/comments/<string:comment_id>': post_comment.PostCommentRoute,
    # '/posts/<string:post_id>/favorites': post_favorite.PostFavoriteRoute,
    # '/posts/<string:post_id>/likes': post_like.PostLikeRoute,
}
