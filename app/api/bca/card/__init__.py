import app.api.bca.card.cards as cards
import app.api.bca.card.card_manage as card_manage
import app.api.bca.card.card_subscribe as card_subscribe

resource_route = {
    '/cards': cards.CardMainRoute,
    '/cards/<int:card_id>': card_manage.CardManagementRoute,
    '/cards/<int:card_id>/subscribe': card_subscribe.CardSubsctiptionRoute,
}
