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
    sns: str = '{\"accounts\": [[\"twitter\", \"TWITTER_USER_ID\"]]}'
    data: dict[str, str] = dataclasses.field(default_factory=lambda: {})

    is_private: bool = False

    created_at: datetime.datetime = datetime.datetime.now()
    modified_at: datetime.datetime = datetime.datetime.now()
    modified: bool = False


class ProfileResponseCase(api_class.ResponseCaseCollector):
    profile_found = api_class.Response(
        description='Profile you requested found.',
        code=200, success=True,
        public_sub_code='profile.result',
        data={"profile": ProfileResponseModel.get_model_openapi_description()})
    multiple_profiles_found = api_class.Response(
        description='Multiple profiles you requested found',
        code=200, success=True,
        public_sub_code='profile.multiple_results',
        data={'profiles': [ProfileResponseModel.get_model_openapi_description()]})
    profile_not_found = api_class.Response(
        description='Profile you requested couldn\'t be found.',
        code=404, success=False,
        public_sub_code='profile.not_found')

    profile_forbidden = api_class.Response(
        description='You don\'t have permissions to do such thing on this profile.',
        code=403, success=False,
        public_sub_code='profile.forbidden')
    profile_prediction_failed = api_class.Response(
        description='Profile has been modified on another device, '
                    'and maybe you tried to modify this profile with old version.',
        code=412, success=False,
        public_sub_code='profile.prediction_failed')

    profile_created = api_class.Response(
        description='We successfully created a profile.',
        code=201, success=True,
        public_sub_code='profile.created',
        data={"profile": ProfileResponseModel.get_model_openapi_description()})
    profile_modified = api_class.Response(
        description='We successfully modified a profile.',
        code=201, success=True,
        public_sub_code='profile.modified',
        data={"profile": ProfileResponseModel.get_model_openapi_description()})
    profile_deleted = api_class.Response(
        description='We successfully deleted a profile.',
        code=204, success=True,
        public_sub_code='profile.deleted')
