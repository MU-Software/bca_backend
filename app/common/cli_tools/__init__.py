import flask

import app.common.cli_tools.openapi_support as openapi_support
import app.common.cli_tools.db_operation as db_operation


def init_app(app: flask.Flask):
    app.cli.add_command(openapi_support.create_openapi_doc)
    app.cli.add_command(db_operation.drop_db)
