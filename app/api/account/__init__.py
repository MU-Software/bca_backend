import app.api.account.signup as signup
import app.api.account.signin as signin
import app.api.account.signout as signout
import app.api.account.deactivate as deactivate
import app.api.account.refresh as refresh
# import app.api.account.token_info as token_info  # DEPRECATED
import app.api.account.duplicate_check as duplicate_check
import app.api.account.email_action as email_action

resource_route = {
    '/account/signup': signup.SignUpRoute,
    '/account/signin': signin.SignInRoute,
    '/account/signout': signout.SignOutRoute,
    '/account/refresh': refresh.AccessTokenIssueRoute,
    '/account/deactivate': deactivate.AccountDeactivationRoute,
    '/account/duplicate': duplicate_check.AccountDuplicateCheckRoute,
    '/account/email/<string:email_token>': email_action.EmailActionRoute,
    # '/account/tokeninfo': token_info.TokenInfoRoute,  # DEPRECATED
}
