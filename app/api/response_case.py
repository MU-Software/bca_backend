import app.api as api


class CommonResponseCase(api.ResponseCaseCollector):
    ping_success = api.Response(
        code=200, success=True,
        public_sub_code='ping.success',
        header=(
            ('X-Recruit-Header', 'Oh, You\'ve found this! '
                                 'How about working together? '
                                 'Please mail us! '
                                 'musoftware(*at*)mudev.cc'),
            ('X-Made-With', 'Python, Flask, SQLAlchemy, PostgreSQL, '
                            'and of course, Linux! '
                            'We proudly use Linux!'),
            ('X-Written-By', 'MUsoftware. Yeah, I\'m writing this '
                             'because I\'m sooo bored :-P '),
        ),
        data={
            'ping': 'pong'
        })

    # Backend error related
    server_error = api.Response(
        code=500, success=False,
        private_sub_code='backend.uncaught_error',
        public_sub_code='backend.error')
    db_error = api.Response(
        # This must be shown as backend error, not a DB error
        # But also, this must be logged as a DB error
        code=500, success=False,
        private_sub_code='backend.db_error',
        public_sub_code='backend.error')

    # Common client-fault mistake related
    body_invalid = api.Response(
        # This will be responsed when user-sent body data is not parsable
        code=400, success=False,
        public_sub_code='request.body.invalid'),
    body_required_omitted = api.Response(
        code=400, success=False,
        public_sub_code='request.body.omitted',
        data={'lacks': []})

    header_invalid = api.Response(
        code=400, success=False,
        public_sub_code='request.header.invalid')
    header_required_omitted = api.Response(
        code=400, success=False,
        public_sub_code='request.header.omitted',
        data={'lacks': []})

    http_mtd_forbidden = api.Response(
        code=403, success=False,
        public_sub_code='http.mtd_forbidden')
    http_not_found = api.Response(
        code=404, success=False,
        public_sub_code='http.not_found')
