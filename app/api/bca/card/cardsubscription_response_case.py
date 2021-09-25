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


class CardSubscriptionResponseCase(api_class.ResponseCaseCollector):
    card_subscribed = api_class.Response(
        description='Target profile successfully subscribes a card',
        code=201, success=True,
        public_sub_code='card.subscribed')
    card_already_subscribed = api_class.Response(
        description='Target profile already subscribed a card',
        code=200, success=True,
        public_sub_code='card.already_subscribed')
    card_unsubscribed = api_class.Response(
        description='Target profile successfully unsubscribes a card',
        code=204, success=True,
        public_sub_code='card.unsubscribed')
    card_not_subscribing = api_class.Response(
        description='Target profile isn\'t subscribing a card',
        code=404, success=False,
        public_sub_code='card.not_subscribing')
