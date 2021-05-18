import dataclasses
import datetime

import app.common.utils as utils
import app.api.helper_class as api_class


@dataclasses.dataclass
class ProfileResponseModel(api_class.ResponseDataModel):
    uuid: int
    name: str
    description: str
    phone: str
    email: str
    sns: str
    data: dict[str, str]

    is_private: bool

    created_at: datetime.datetime
    modified_at: datetime.datetime
    modified: bool


class ProfileResponseCase(api_class.ResponseCaseCollector):
    profile_found = api_class.Response(
        description='Profile you requested found.',
        code=200, success=True,
        public_sub_code='profile.result',
        data=ProfileResponseModel.get_model_openapi_description())
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
        code=401, success=False,
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
        data=ProfileResponseModel.get_model_openapi_description())
    profile_modified = api_class.Response(
        description='We successfully modified a profile.',
        code=201, success=True,
        public_sub_code='profile.modified',
        data=ProfileResponseModel.get_model_openapi_description())
    profile_deleted = api_class.Response(
        description='We successfully deleted a profile.',
        code=204, success=True,
        public_sub_code='profile.deleted')
