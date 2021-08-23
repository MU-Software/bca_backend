import app.api.bca.profile.profiles as profiles
import app.api.bca.profile.profile_manage as profile_manage
import app.api.bca.profile.cards as cards
import app.api.bca.profile.card_manage as card_manage
import app.api.bca.profile.card_subscribe as card_subscribe

resource_route = {
    '/profiles/': profiles.ProfileMainRoute,
    '/profiles/<int:profile_id>': profile_manage.ProfileManagementRoute,
    '/profiles/<int:profile_id>/cards': cards.CardMainRoute,
    '/profiles/<int:profile_id>/cards/<int:card_id>': card_manage.CardManagementRoute,
    '/profiles/<int:profile_id>/cards/<int:card_id>/subscribe': card_subscribe.CardSubsctiptionRoute,
}
