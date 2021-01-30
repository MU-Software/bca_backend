# Request handler
def before_first_request():
    pass


def before_request():
    pass


def after_request(response):
    print('After response executed!')
    # print(dir(response))
    return response


def teardown_request(exception):
    pass


def teardown_appcontext(exception):
    pass


# Register all request handler
def register_request_handler(app):
    app.before_first_request(before_first_request)
    app.before_request(before_request)
    app.after_request(after_request)
    app.teardown_request(teardown_request)
    app.teardown_appcontext(teardown_appcontext)
