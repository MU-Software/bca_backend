import dataclasses
import datetime

import app.api.helper_class as api_class


@dataclasses.dataclass
class ProfileResponseModel(api_class.ResponseDataModel):
    uuid: int = 0
    name: str = 'PROFILE_NAME'
    description: str = 'SOME_DESCRIPTION'
    phone: str = '010-0000-0000'
    email: str = 'example@example.com'
    sns: str = '\"twitter\": \"TWITTER_USER_ID\"'
    data: dict[str, str] = dataclasses.field(default_factory=lambda: {})

    is_private: bool = False

    created_at: datetime.datetime = datetime.datetime.now()
    modified_at: datetime.datetime = datetime.datetime.now()
    modified: bool = False


class ProfileRelationResponseCase(api_class.ResponseCaseCollector):
    profilerelation_follows = api_class.Response(
        description='Requested profile follows this profile',
        code=200, success=True,  # Set code to 201 when relations are created, not modified
        public_sub_code='profilerelation.follows')
    profilerelation_follow_requests = api_class.Response(
        description='Requested profile requested follow on this profile',
        code=200, success=True,  # Set code to 201 when relations are created, not modified
        public_sub_code='profilerelation.follow_requests')
    profilerelation_blocks = api_class.Response(
        description='Requested profile blocks this profile',
        code=200, success=True,  # Set code to 201 when relations are created, not modified
        public_sub_code='profilerelation.blocks')
    profilerelation_hides = api_class.Response(
        description='Requested profile hides this profile',
        code=200, success=True,
        public_sub_code='profilerelation.hides')
    profilerelation_cut_off = api_class.Response(
        description='Requested profile now cuts off relationship with this profile',
        code=204, success=True,
        public_sub_code='profilerelation.cut_off')

    profilerelation_in_follow_request_state = api_class.Response(
        description='You are on a follow-request state with this profile',
        code=409, success=False,
        public_sub_code='profilerelation.in_follow_request_state')
    profilerelation_already_in_state = api_class.Response(
        description='You are already on requested state with this profile',
        code=409, success=False,
        public_sub_code='profilerelation.already_on_state')

    profilerelation_not_related = api_class.Response(
        description='You aren\'t on any relationship with this profile',
        code=404, success=False,
        public_sub_code='profilerelation.not_related')
