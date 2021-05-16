import app.api.profiles.profiles as profiles
import app.api.profiles.profile_manage as profile_manage
import app.api.profiles.cards as cards
import app.api.profiles.card_manage as card_manage
import app.api.profiles.card_subscribe as card_subscribe

resource_route = {
    '/profiles/': profiles.ProfileMainRoute,
    '/profiles/<int:profile_id>': profile_manage.ProfileManagementRoute,
    '/profiles/<int:profile_id>/cards': cards.CardMainRoute,
    '/profiles/<int:profile_id>/cards/<int:card_id>': card_manage.CardManagementRoute,
    '/profiles/<int:profile_id>/cards/<int:card_id>/subscrie': card_subscribe,
}
