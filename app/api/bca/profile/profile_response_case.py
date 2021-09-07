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


class ProfileResponseCase(api_class.ResponseCaseCollector):
    profile_followed = api_class.Response(
        description='Successfully followed this profile',
        code=201, success=True,
        public_sub_code='profile.followed')
    profile_already_followed = api_class.Response(
        description='You are already following this profile',
        code=201, success=True,
        public_sub_code='profile.already_followed')
    profile_unfollowed = api_class.Response(
        description='Successfully unfollowed this profile',
        code=204, success=True,
        public_sub_code='profile.unfollowed')
    profile_not_following = api_class.Response(
        description='You aren\'t following this profile',
        code=404, success=False,
        public_sub_code='profile.not_following')
