import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging
import flask

import app.common.utils as utils


def firebase_send_notify(title: str = None, body: str = None, data: dict = None,
                         topic: str = None, target_token: str = None):
    try:
        cred = credentials.Certificate(flask.current_app.config.get('FIREBASE_CERTIFICATE'))
        default_app = firebase_admin.initialize_app(cred)  # noqa
    except ValueError:
        # default_app is already initialized.
        pass

    if not any((title, body, data)):
        raise ValueError('At least one of (title, body)|data must be set')

    data = data if data else {'click_action': 'FLUTTER_NOTIFICATION_CLICK', }
    # all keys and values in data must be a string.
    tmp_dict = dict()
    safe_str = utils.ignore_exception(Exception, '')(str)
    for k, v in data.items():
        tmp_dict[str(k)] = safe_str(v)
    data = tmp_dict

    notification = None
    if any((title, body)):
        title = str(title) or ''
        body = str(body) or ''
        notification = messaging.Notification(title=title, body=body)

    message = messaging.Message(
        data=data,
        notification=notification,

        # android=messaging.AndroidConfig(
        #     ttl=datetime.timedelta(seconds=3600),
        #     priority='normal',
        # ),
        # apns=None,
        # webpush=None,

        token=target_token,
        topic=topic,
        # fcm_options=None,
        # condition=None,
    )

    response = messaging.send(message)
    print('Successfully sent message:', response)  # Response is a message ID string.
