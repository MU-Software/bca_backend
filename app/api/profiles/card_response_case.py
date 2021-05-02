import app.api.helper_class as api_class


class CardResponseCase(api_class.ResponseCaseCollector):
    card_found = api_class.Response(
        description='Card you requested found.',
        code=200, success=True,
        public_sub_code='card.result')
    card_not_found = api_class.Response(
        description='Card you requested couldn\'t be found.',
        code=404, success=False,
        public_sub_code='card.not_found')
    # card_list = api_class.Response(
    #     description='This is a list of cards.',
    #     code=200, success=True,
    #     public_sub_code='card.list')

    card_forbidden = api_class.Response(
        description='You don\'t have permissions to do such thing on this card.',
        code=401, success=False,
        public_sub_code='card.forbidden')
    card_prediction_failed = api_class.Response(
        description='Card has been modified on another device, and you tried to modify this card with old version.',
        code=412, success=False,
        public_sub_code='card.prediction_failed')

    card_created = api_class.Response(
        description='We successfully created a card.',
        code=201, success=True,
        public_sub_code='card.created',
        data={'id': 0})
    card_modified = api_class.Response(
        description='We successfully modified a card.',
        code=201, success=True,
        public_sub_code='card.modified',
        data={'id': 0})
    card_deleted = api_class.Response(
        description='We successfully deleted a card.',
        code=204, success=True,
        public_sub_code='card.deleted',
        data={'id': 0})
