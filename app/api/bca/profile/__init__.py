import app.api.bca.profile.profiles as profiles
import app.api.bca.profile.profile_manage as profile_manage
import app.api.bca.profile.profile_card as profile_card
import app.api.bca.profile.profile_follow as profile_follow
import app.api.bca.profile.profile_follower_following as profile_follower_following

resource_route = {
    '/profiles/': profiles.ProfileMainRoute,
    '/profiles/<int:profile_id>': profile_manage.ProfileManagementRoute,
    '/profiles/<int:profile_id>/cards': profile_card.ProfileCardRoute,
    '/profiles/<int:profile_id>/follow': profile_follow.ProfileFollowRoute,
    '/profiles/<int:profile_id>/follower': profile_follower_following.ProfileFollowerRoute,
    '/profiles/<int:profile_id>/following': profile_follower_following.ProfileFollowingRoute,
}
