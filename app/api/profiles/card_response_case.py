import dataclasses
import datetime

import app.api.helper_class as api_class


@dataclasses.dataclass
class CardResponseModel(api_class.ResponseDataModel):
    uuid: int = 0
    profile_name: str = 'PROFILE_NAME'
    card_name: str = 'CARD_NAME'
    data: dict[str, str] = dataclasses.field(default_factory=lambda: {})
    preview_url: str = ''

    created_at: datetime.datetime = datetime.datetime.now()
    modified_at: datetime.datetime = datetime.datetime.now()
    modified: bool = False


class CardResponseCase(api_class.ResponseCaseCollector):
    card_found = api_class.Response(
        description='Card you requested found.',
        code=200, success=True,
        public_sub_code='card.result',
        data={'card': CardResponseModel.get_model_openapi_description()})
    multiple_cards_found = api_class.Response(
        description='Multiple cards you requested found',
        code=200, success=True,
        public_sub_code='card.multiple_results',
        data={'cards': [CardResponseModel.get_model_openapi_description()]})
    card_not_found = api_class.Response(
        description='Card you requested couldn\'t be found.',
        code=404, success=False,
        public_sub_code='card.not_found')

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
        data={'card': CardResponseModel.get_model_openapi_description()})
    card_modified = api_class.Response(
        description='We successfully modified a card.',
        code=201, success=True,
        public_sub_code='card.modified',
        data={'card': CardResponseModel.get_model_openapi_description()})
    card_deleted = api_class.Response(
        description='We successfully deleted a card.',
        code=204, success=True,
        public_sub_code='card.deleted')

    card_subscribed = api_class.Response(
        description='Target profile successfully subscribes a card',
        code=201, success=True,
        public_sub_code='card.subscribed')
    card_already_subscribed = api_class.Response(
        description='Target profile already subscribed a card',
        code=201, success=True,
        public_sub_code='card.already_subscribed')
    card_unsubscribed = api_class.Response(
        description='Target profile successfully unsubscribes a card',
        code=204, success=True,
        public_sub_code='card.unsubscribed')
    card_not_subscribing = api_class.Response(
        description='Target profile isn\'t subscribing a card',
        code=404, success=False,
        public_sub_code='card.not_subscribing')
