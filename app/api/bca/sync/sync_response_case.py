import app.api.helper_class as api_class


class SyncResponseCase(api_class.ResponseCaseCollector):
    sync_ok = api_class.Response(
        description='Your profile/card db file is outdated, '
                    'so we sent you a new version of db file.',
        code=200, success=True,
        public_sub_code='sync.ok',
        data={'db': ''})
    sync_recreated = api_class.Response(
        description='Your profile/card db file is recreated.',
        code=200, success=True,
        public_sub_code='sync.recreated',
        data={'db': ''})

    sync_latest = api_class.Response(
        description='Your profile/card db file is latest version.',
        code=304, success=True,
        public_sub_code='sync.latest')
