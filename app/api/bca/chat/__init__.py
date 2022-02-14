import app.api.bca.chat.chats as chats
import app.api.bca.chat.chat_manage as chat_manage
import app.api.bca.chat.chat_event as chat_event

resource_route = {
    '/chats/': chats.ChatRoute,
    '/chats/<int:room_id>': chat_manage.ChatManageRoute,
    '/chats/<int:room_id>/events/<int:event_id>': {
        'view_func': chat_event.ChatEventRoute,
        'base_path': '/chats/<int:room_id>/events/',
        'defaults': {'event_id': None},
    },
}
