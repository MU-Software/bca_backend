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

    deleted = db.Column(db.Boolean, default=False, nullable=False)
    private = db.Column(db.Boolean, default=False, nullable=False)

    commentable = db.Column(db.Boolean, default=True, nullable=False)
    readable = db.Column(db.Boolean, default=True, nullable=False)
    modifiable = db.Column(db.Boolean, default=True, nullable=False)

    comments: list['Comment'] = None  # Placeholder for backref


class Comment(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_COMMENT'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_Comment_UUID'),
                     primary_key=True)

    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'))
    user = db.relationship('User', backref=db.backref('comments', order_by='Comment.modified_at.desc()'))

    post_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_POST.uuid'))
    post = db.relationship('Post', backref=db.backref('comments', order_by='Comment.created_at.desc()'))

    body = db.Column(db.String, unique=False, nullable=False)

    deleted = db.Column(db.Boolean, default=False, nullable=False)
    private = db.Column(db.Boolean, default=False, nullable=False)

    readable = db.Column(db.Boolean, default=True, nullable=False)
    modifiable = db.Column(db.Boolean, default=True, nullable=False)
    deletable = db.Column(db.Boolean, default=True, nullable=False)
