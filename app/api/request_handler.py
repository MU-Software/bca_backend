import flask
import werkzeug.exceptions

from app.api.response_case import CommonResponseCase


# Request handler
def before_first_request():
    pass


def before_request():
    pass


def after_request(response):
    # print('After response executed!')
    # print(dir(response))
    return response


def teardown_request(exception):
    pass


def teardown_appcontext(exception):
    pass


# Register all request handler
def register_request_handler(app: flask.Flask):
    app.before_first_request(before_first_request)
    app.before_request(before_request)
    app.after_request(after_request)
    app.teardown_request(teardown_request)
    app.teardown_appcontext(teardown_appcontext)

    @app.errorhandler(404)
    def handle_404(exception: werkzeug.exceptions.HTTPException):
        response = exception.get_response()
        result_body, result_code, result_header = CommonResponseCase.http_not_found.create_response()
        response.body = result_body
        response.code = result_code
        for header in result_header:
            response.headers.add(*header)
        response.content_type = 'application/json'
        return response

    @app.errorhandler(405)
    def handle_405(exception: werkzeug.exceptions.HTTPException):
        response = exception.get_response()
        result_body, result_code, result_header = CommonResponseCase.http_mtd_forbidden.create_response()
        response.body = result_body
        response.code = result_code
        for header in result_header:
            response.headers.add(*header)
        response.content_type = 'application/json'
        return response

    @app.errorhandler(Exception)
    def handle_exception(exception: werkzeug.exceptions.HTTPException):
        response = exception.get_response()
        result_body, result_code, result_header = CommonResponseCase.server_error.create_response()
        # result_body['code'] = response.code
        # result_code = response.code

        response.body = result_body
        response.code = result_code
        for header in result_header:
            response.headers.add(*header)
        response.content_type = 'application/json'
        return response


