import flask

import app.common.cli_tools.db_operation as db_operation


def init_app(app: flask.Flask):
    app.cli.add_command(db_operation.drop_db)
