import app.api.helper_class as api_class


class ProfileResponseCase(api_class.ResponseCaseCollector):
    profile_found = api_class.Response(
        description='Profile you requested found.',
        code=200, success=True,
        public_sub_code='profile.result')
    multiple_profiles_found = api_class.Response(
        description='Multiple profiles you requested found',
        code=200, success=True,
        public_sub_code='profile.multiple_results')
    profile_not_found = api_class.Response(
        description='Profile you requested couldn\'t be found.',
        code=404, success=False,
        public_sub_code='profile.not_found')
    profile_list = api_class.Response(
        description='This is a list of profiles.',
        code=200, success=True,
        public_sub_code='profile.list')

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
        data={'id': 0})
    profile_modified = api_class.Response(
        description='We successfully modified a profile.',
        code=201, success=True,
        public_sub_code='profile.modified',
        data={'id': 0})
    profile_deleted = api_class.Response(
        description='We successfully deleted a profile.',
        code=204, success=True,
        public_sub_code='profile.deleted',
        data={'id': 0})
