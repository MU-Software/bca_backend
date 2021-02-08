import app.database as db_module
import app.database.user as user_module

db = db_module.db


class Board(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_BOARD'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_Board_UUID'),
                     primary_key=True,
                     nullable=False)

    name = db.Column(db.String, unique=False, nullable=False)
    board_type = db.Column(db.String, default='normal', nullable=False)
    description = db.Column(db.String, unique=False, nullable=False)

    deleted = db.Column(db.Boolean, default=False, nullable=False)
    private = db.Column(db.Boolean, default=False, nullable=False)

    commentable = db.Column(db.Boolean, default=True, nullable=False)
    readable = db.Column(db.Boolean, default=True, nullable=False)
    writeable = db.Column(db.Boolean, default=True, nullable=False)

    posts: list['Post'] = None  # Placeholder for backref


class Post(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_POST'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_Post_UUID'),
                     primary_key=True,
                     nullable=False)

    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'))
    user: user_module.User = db.relationship('User', backref=db.backref('posts', order_by='Post.modified_at.desc()'))

    board_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_BOARD.uuid'))
    board: 'Board' = db.relationship('Board', backref=db.backref('posts', order_by='Post.created_at.desc()'))

    title = db.Column(db.String, unique=False, nullable=False)
    body = db.Column(db.String, unique=False, nullable=False)
    announcement = db.Column(db.Boolean, default=False, nullable=False)

    # if post locked, then anyone cannot read/modify/delete/comment this, and this must not be shown on list.
    # This looks quite same as deleted, but...
    #   - cannot be garbage collected
    #   - cannot recover by admin
    #   - only can be accessed by DB manager
    locked = db.Column(db.Boolean, default=False, nullable=False)
    locked_at = db.Column(db.DateTime, nullable=True)

    deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    private = db.Column(db.Boolean, default=False, nullable=False)

    commentable = db.Column(db.Boolean, default=True, nullable=False)
    readable = db.Column(db.Boolean, default=True, nullable=False)
    modifiable = db.Column(db.Boolean, default=True, nullable=False)

    comments: list['Comment'] = None  # Placeholder for backref
    favorited_by: list['PostFavorite'] = None  # Placeholder for backref
    liked_by: list['PostLike'] = None  # Placeholder for backref
    tags: list['PostTagRelation'] = None  # Placeholder for backref


class Comment(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_COMMENT'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_Comment_UUID'),
                     primary_key=True)

    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'))
    user = db.relationship('User', backref=db.backref('comments', order_by='Comment.modified_at.desc()'))

    post_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_POST.uuid'))
    post: 'Post' = db.relationship('Post',
                                   backref=db.backref(
                                        'comments',
                                        order_by='Comment.created_at.desc()'))

    body = db.Column(db.String, unique=False, nullable=False)

    deleted = db.Column(db.Boolean, default=False, nullable=False)
    private = db.Column(db.Boolean, default=False, nullable=False)

    readable = db.Column(db.Boolean, default=True, nullable=False)
    modifiable = db.Column(db.Boolean, default=True, nullable=False)
    deletable = db.Column(db.Boolean, default=True, nullable=False)


class Tag(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_TAG'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_Tag_UUID'),
                     primary_key=True,
                     nullable=False)
    name = db.Column(db.String, unique=True, nullable=False)


class PostTagRelation(db.Model):
    __tablename__ = 'TB_POST_TAG_RELATION'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_PostTagRelation_UUID'),
                     primary_key=True,
                     nullable=False)
    name = db.Column(db.String, unique=True, nullable=False)

    post_id = db.Column(db_module.PrimaryKeyType,
                        db.ForeignKey('TB_POST.uuid'),
                        nullable=False)
    post: 'Post' = db.relationship('Post',
                                   backref=db.backref(
                                        'tags',
                                        order_by='PostTagRelation.created_at.desc()'))

    tag_id = db.Column(db_module.PrimaryKeyType,
                       db.ForeignKey('TB_TAG.uuid'),
                       nullable=False)
    tag: 'Tag' = db.relationship('Tag',
                                 backref=db.backref(
                                    'posts',
                                    order_by='PostTagRelation.created_at.desc()'))


class PostLike(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_POST_LIKE'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_PostLike_UUID'),
                     primary_key=True,
                     nullable=False)

    post_id = db.Column(db_module.PrimaryKeyType,
                        db.ForeignKey('TB_POST.uuid'),
                        nullable=False)
    post: 'Post' = db.relationship('Post',
                                   backref=db.backref(
                                        'liked_by',
                                        order_by='PostLike.created_at.desc()'))

    user_id = db.Column(db_module.PrimaryKeyType,
                        db.ForeignKey('TB_USER.uuid'),
                        nullable=False)
    user: 'user_module.User' = db.relationship('User',
                                               backref=db.backref(
                                                    'liked_on',
                                                    order_by='PostLike.created_at.desc()'))


class PostFavorite(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_POST_FAVORITE'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_PostFavorite_UUID'),
                     primary_key=True,
                     nullable=False)

    post_id = db.Column(db_module.PrimaryKeyType,
                        db.ForeignKey('TB_POST.uuid'),
                        nullable=False)
    post: 'Post' = db.relationship('Post',
                                   backref=db.backref(
                                        'favorited_by',
                                        order_by='PostFavorite.created_at.desc()'))

    user_id = db.Column(db_module.PrimaryKeyType,
                        db.ForeignKey('TB_USER.uuid'),
                        nullable=False)
    user: 'user_module.User' = db.relationship('User',
                                               backref=db.backref(
                                                    'favorited_on',
                                                    order_by='PostFavorite.created_at.desc()'))
