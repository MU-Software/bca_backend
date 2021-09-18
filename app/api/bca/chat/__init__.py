import app.api.bca.chat.chats as chats
import app.api.bca.chat.chat_manage as chat_manage

resource_route = {
    '/chats/': chats.ChatRoute,
    '/chats/<int:room_id>': chat_manage.ChatManageRoute,
}
