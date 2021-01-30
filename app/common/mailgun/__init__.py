import flask

import app.common.mailgun.gmail as gmail_support

gmail_send_mail = lambda fromaddr, toaddr, subject, message: gmail_support.send_mail(  # noqa
    google_client_id=flask.current_app.config.get('GOOGLE_CLIENT_ID'),
    google_client_secret=flask.current_app.config.get('GOOGLE_CLIENT_SECRET'),
    google_refresh_token=flask.current_app.config.get('GOOGLE_REFRESH_TOKEN'),
    fromaddr=fromaddr, toaddr=toaddr, subject=subject, message=message,
    show_debug=True
)
