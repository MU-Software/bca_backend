import flask
import flask.views
import os

import app.config as config


def create_app():
    app = flask.Flask(__name__,
                      instance_relative_config=True,
                      template_folder='static/template')

    environment = os.environ.get('FLASK_ENV', 'production')
    app.config.from_object(config.config_by_name[environment])

    with app.app_context():
        import app.database as db
        db.init_app(app)

        import app.api as api
        api.init_app(app)

        import app.admin as admin
        admin.init_app(app)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run()
