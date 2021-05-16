import datetime
import flask
import flask.views
import typing

import app.api.helper_class as api_class
import app.common.utils as utils
import app.database as db_module
import app.database.jwt as jwt_module
import app.database.profile as profile_module

from app.api.response_case import CommonResponseCase
from app.api.profiles.profile_response_case import ProfileResponseCase


class ProfileManagementRoute(flask.views.MethodView, api_class.MethodViewMixin):
    @api_class.RequestHeader(
        required_fields={},
        optional_fields={'X-Csrf-Token': {'type': 'string', }, },
        auth={api_class.AuthType.Bearer: False, })
    def get(self,
            profile_id: int,
            req_header: dict,
            access_token: typing.Optional[jwt_module.AccessToken] = None):
        '''
        description: Get profile data of given UUID
        responses:
            - profile_found
            - profile_not_found
            - profile_forbidden
            - server_error
        '''
        try:
            target_profile: profile_module.Profile = profile_module.Profile.query\
                .filter(profile_module.Profile.locked_at != None)\
                .filter(profile_module.Profile.uuid == int(profile_id))\
                .first()  # noqa
            if not target_profile:
                return ProfileResponseCase.profile_not_found.create_response()

            if target_profile.private or target_profile.deleted_at is not None:
                # Check if profile is user's or user already subscribed this profile's card,
                # this will check only if access token is given, if not, then this will be failed.
                if not access_token:
                    return ProfileResponseCase.profile_forbidden.create_response()

                if access_token.role not in ('admin', ) and target_profile.user_id != access_token.user:
                    # Find all target profile's card, and find any relations of requested user and those cards
                    profile_subscription_subquery_1 = profile_module.Card.query\
                        .filter(profile_module.Card.profile_id == target_profile.uuid)\
                        .filter(profile_module.Card.locked_at != None)\
                        .subquery()  # noqa
                    profile_subscription_subquery_2 = profile_module.Profile.query\
                        .filter(profile_module.Profile.user_id == access_token.user)\
                        .filter(profile_module.Card.locked_at != None)\
                        .filter(profile_module.Card.deleted_at != None)\
                        .subquery()  # noqa
                    profile_subscription = profile_module.CardSubscribed.query\
                        .filter(profile_module.CardSubscribed.card_id.in_(profile_subscription_subquery_1))\
                        .filter(profile_module.CardSubscribed.profile_id.in_(profile_subscription_subquery_2))\
                        .scalar()
                    if not profile_subscription:
                        return ProfileResponseCase.profile_forbidden.create_response()

            return ProfileResponseCase.profile_found.create_response(
                data={'profile': target_profile.to_dict(), },
                header=(('ETag', target_profile.commit_id), ))
        except Exception:
            return CommonResponseCase.server_error.create_response()

    # # Modify post
    # def patch(self, post_id: int):
    #     post_req = utils.request_body(
    #         required_fields=[],
    #         optional_fields=[
    #             'title', 'body',
    #             'announcement', 'private', 'commentable'])
    #     if type(post_req) == list:
    #         return CommonResponseCase.body_required_omitted.create_response(data={'lacks': post_req})
    #     elif post_req is None:
    #         return CommonResponseCase.body_invalid.create_response()
    #     elif not post_req:
    #         return CommonResponseCase.body_empty.create_response()
    #     elif type(post_req) != dict:
    #         return CommonResponseCase.body_invalid.create_response()

    #     target_post: board_module.Post = None
    #     try:
    #         target_post = board_module.Post.query\
    #             .filter(board_module.Post.locked == False)\
    #             .filter(board_module.Post.deleted == False)\
    #             .filter(board_module.Post.uuid == int(post_id)).first()
    #     except Exception:
    #         return CommonResponseCase.db_error.create_response()
    #     if not target_post:
    #         return PostResponseCase.post_not_found.create_response()

    #     # Check requested user is author
    #     access_token: jwt_module.AccessToken = jwt_module.get_account_data()

    #     if not access_token:
    #         if access_token is False:
    #             return AccountResponseCase.access_token_expired.create_response()
    #         return AccountResponseCase.access_token_invalid.create_response()

    #     # Check Etag
    #     if req_etag := flask.request.headers.get('If-Match', False):
    #         if req_etag != target_post.commit_id:
    #             return PostResponseCase.post_prediction_failed.create_response()
    #     elif req_modified_at := flask.request.headers.get('If-Unmodified-Since', False):
    #         try:
    #             req_modified_at = datetime.datetime.strptime(req_modified_at, '%a, %d %b %Y %H:%M:%S GMT')
    #             if target_post.modified_at > req_modified_at:
    #                 return PostResponseCase.post_prediction_failed.create_response()
    #         except Exception:
    #             return CommonResponseCase.header_invalid.create_response()
    #     else:
    #         return CommonResponseCase.header_required_omitted.create_response(data={'lacks': ['ETag', ]})

    #     # Is req_user author? (author cannot modify post when post is not modifiable)
    #     if (target_post.user_id != access_token.user) or (not target_post.modifiable):
    #         return PostResponseCase.post_forbidden.create_response()

    #     try:
    #         # Modify post using request body
    #         for req_key, req_value in post_req.items():
    #             setattr(target_post, req_key, req_value)
    #         db_module.db.session.commit()

    #         return PostResponseCase.post_modified.create_response()
    #     except Exception:
    #         return CommonResponseCase.db_error.create_response()

    @api_class.RequestHeader(
        required_fields={
            'X-Csrf-Token': {'type': 'string', },
            'If-Match': {'type': 'string', },
        },
        auth={api_class.AuthType.Bearer: True, })
    def delete(self,
               profile_id: int,
               req_header: dict,
               access_token: jwt_module.AccessToken):
        '''
        description: Delete user's {profile_id} profile
        responses:
            - profile_deleted
            - profile_not_found
            - profile_forbidden
            - profile_prediction_failed
            - header_invalid
            - header_required_omitted
            - server_error
        '''
        try:
            target_profile: profile_module.Profile = profile_module.Profile.query\
                .filter(profile_module.Profile.locked_at == None)\
                .filter(profile_module.Profile.deleted_at == None).first()  # noqa
            if not target_profile:
                return ProfileResponseCase.profile_not_found.create_response()
            if target_profile.user_id != access_token.user:
                # Check requested user is the owner of the profile
                return ProfileResponseCase.profile_forbidden.create_response()

            # Check Etag
            if req_header['If-Match'] != target_profile.commit_id:
                return ProfileResponseCase.profile_prediction_failed.create_response()

            # Delete this profile
            target_profile.deleted_at = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)
            target_profile.deleted_by_id = access_token.user
            db_module.db.session.commit()

            return ProfileResponseCase.profile_deleted.create_response()
        except Exception:
            # TODO: Check DB error
            return CommonResponseCase.server_error.create_response()
