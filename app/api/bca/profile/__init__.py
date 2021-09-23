import app.api.bca.profile.profiles as profiles
import app.api.bca.profile.profile_manage as profile_manage
import app.api.bca.profile.profile_card as profile_card
import app.api.bca.profile.profile_relation as profile_relation
import app.api.bca.profile.profile_follow_request as profile_follow_request

resource_route = {
    '/profiles/': profiles.ProfileMainRoute,
    '/profiles/<int:profile_id>': profile_manage.ProfileManagementRoute,
    '/profiles/<int:profile_id>/cards': profile_card.ProfileCardRoute,
    '/profiles/<int:profile_id>/relations': profile_relation.ProfileRelationRoute,
    '/profiles/<int:profile_id>/follow-request': profile_follow_request.ProfileFollowRequestRoute,
}
