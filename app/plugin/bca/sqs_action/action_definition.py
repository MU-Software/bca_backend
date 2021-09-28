import typing

import app.database as db_module
import app.database.bca.profile as profile_module
import app.plugin.bca.database.user_db_table as user_db_table
import app.plugin.bca.sqs_action as sqs_action

db = db_module.db

# User DB definition, add declared_attr columns too
UserDB_ProfileTable_Columns = user_db_table.Profile.column_names
UserDB_ProfileRelationTable_Columns = user_db_table.ProfileRelation.column_names
UserDB_CardTable_Columns = user_db_table.Card.column_names
UserDB_CardSubscriptionTable_Columns = user_db_table.CardSubscription.column_names


def profile_created(profile_row: profile_module.Profile):
    # Do task to user that created this profile
    model_created: dict[str, typing.Any] = {k: getattr(profile_row, k) for k in UserDB_ProfileTable_Columns}
    sqs_action.UserDBModifyTaskMessage(
        profile_row.user_id,
        [sqs_action.UserDBModifyData(
            'TB_PROFILE',
            profile_row.uuid,
            sqs_action.UserDBModifyActionCase.add,
            model_created), ]).add_to_queue()


def profile_modified(
        profile_row: profile_module.Profile,
        profile_row_changeset: dict[str, list[typing.Any, typing.Any]]):
    # Do task to all followers of this profile

    # Calculate changes and filter it.
    # We need to calculate changeset outside of function,
    # because some data have to be gotten before service-db-commit,
    # and some data have to be gotten *after* service-db-commit.
    model_changes = {k: v[1] for k, v in profile_row_changeset.items() if k in UserDB_ProfileTable_Columns}

    # Calculate followers(target users) by
    #   1. Query this profile's cards
    #   2. Find subscribers of those cards
    #   3. Get distinct user uuid of those subscribers

    # 1. Querying this profile's cards
    subquery_cards_of_profile = db.session.query(profile_module.Card.uuid)\
        .filter(profile_module.Card.locked_at.is_(None))\
        .filter(profile_module.Card.profile_id == profile_row.uuid)\
        .subquery()

    # 2. Find all subscribers of cards that created by profile_id
    subquery_subscribing_profiles_of_cards_of_profile = db.session.query(profile_module.CardSubscription.profile_id)\
        .filter(profile_module.CardSubscription.card_id.in_(subquery_cards_of_profile))\
        .subquery()

    # 3. Get distinct user uuid of those subscribers
    query_user_uuid_of_followers_of_modified_profile = db.session.query(profile_module.Profile.user_id)\
        .filter(profile_module.Profile.locked_at.is_(None))\
        .filter(profile_module.Profile.uuid.in_(subquery_subscribing_profiles_of_cards_of_profile))\
        .distinct().order_by(profile_module.Profile.user_id)

    target_list_of_user_uuid: list[int] = [z[0] for z in query_user_uuid_of_followers_of_modified_profile.all()]
    target_list_of_user_uuid = target_list_of_user_uuid or list()
    target_list_of_user_uuid.append(profile_row.user_id)  # Add profile owner himself/herself

    # User DB modify data
    task_data = sqs_action.UserDBModifyData(
                    'TB_PROFILE',
                    profile_row.uuid,
                    sqs_action.UserDBModifyActionCase.modify,
                    model_changes)

    for target_user in target_list_of_user_uuid:
        sqs_action.UserDBModifyTaskMessage(target_user, [task_data, ]).add_to_queue()


def card_created(card_row: profile_module.Card):
    # Do task to user that created this card
    target_user = card_row.profile.user_id
    model_created: dict[str, typing.Any] = {k: getattr(card_row, k) for k in UserDB_CardTable_Columns}
    sqs_action.UserDBModifyTaskMessage(
        target_user,
        [sqs_action.UserDBModifyData(
            'TB_CARD',
            target_user,
            sqs_action.UserDBModifyActionCase.add,
            model_created), ]).add_to_queue()


def card_modified(
        card_row: profile_module.Card,
        card_row_changeset: dict[str, list[typing.Any, typing.Any]]):
    # Do task to all subscribers of this card

    # Calculate changes and filter it.
    # We need to calculate changeset outside of function,
    # because some data have to be gotten before service-db-commit,
    # and some data have to be gotten *after* service-db-commit.
    model_changes = {k: v[1] for k, v in card_row_changeset.items() if k in UserDB_CardTable_Columns}

    # 1. Find all subscribers of this card
    subquery_subscribing_profiles_of_cards = db.session.query(profile_module.CardSubscription.profile_id)\
        .filter(profile_module.CardSubscription.card_id == card_row.uuid)\
        .subquery()
    # 2. Get all user uuid of those subscribers
    query_user_uuid_of_subscribers = db.session.query(profile_module.Profile.user_id)\
        .filter(profile_module.Profile.locked_at.is_(None))\
        .filter(profile_module.Profile.uuid.in_(subquery_subscribing_profiles_of_cards))\
        .distinct().order_by(profile_module.Profile.user_id)

    target_list_of_user_uuid: list[int] = [z[0] for z in query_user_uuid_of_subscribers.all()]
    target_list_of_user_uuid = target_list_of_user_uuid or list()
    target_list_of_user_uuid.append(card_row.profile.user_id)  # Add profile owner himself/herself

    # User DB modify data
    task_data = sqs_action.UserDBModifyData(
                    'TB_CARD',
                    card_row.uuid,
                    sqs_action.UserDBModifyActionCase.modify,
                    model_changes)

    for target_user in target_list_of_user_uuid:
        sqs_action.UserDBModifyTaskMessage(target_user, [task_data, ]).add_to_queue()


def card_subscribed(
        card_subscription: profile_module.CardSubscription,
        card_data: typing.Union[profile_module.Card] = None,
        profile_data: typing.Union[profile_module.Profile] = None):
    # Do task to new subscriber
    if card_data is None:
        # Do query of subscribed card
        card_data = profile_module.Card.query\
            .filter(profile_module.Card.uuid == card_subscription.card_id).first()
        if not card_data:
            raise Exception('Card not found while creating task. How could this happened?')

    if profile_data is None:
        # Do query of following profile
        profile_data = profile_module.Profile.query\
            .filter(profile_module.Profile.uuid == card_data.profile_id).first()
        if not profile_data:
            raise Exception('Profile not found while creating task. How could this happened?')

    # Create task data
    task_card_data = {k: getattr(card_data, k) for k in UserDB_CardTable_Columns}
    task_card_data = sqs_action.UserDBModifyData(
        'TB_CARD',
        card_data.uuid,
        sqs_action.UserDBModifyActionCase.add,
        task_card_data)
    task_profile_data = {k: getattr(profile_data, k) for k in UserDB_ProfileTable_Columns}
    task_profile_data = sqs_action.UserDBModifyData(
        'TB_PROFILE',
        profile_data.uuid,
        sqs_action.UserDBModifyActionCase.add,
        task_profile_data)
    task_cardsubscription_data = {k: getattr(card_subscription, k) for k in UserDB_CardSubscriptionTable_Columns}
    task_cardsubscription_data = sqs_action.UserDBModifyData(
        'TB_CARD_SUBSCRIPTION',
        card_subscription.uuid,
        sqs_action.UserDBModifyActionCase.add,
        task_cardsubscription_data)

    sqs_action.UserDBModifyTaskMessage(
        card_subscription.profile.user_id,
        [task_card_data, task_profile_data, task_cardsubscription_data]).add_to_queue()


def card_unsubscribed(card_subscription: profile_module.CardSubscription):
    # Do task to this unscriber
    # Delete TB_CARD_SUBSCRIPTION row, as this user isn't subscribing this card anymore
    # TODO: Need to GC TB_PROFILE and TB_CARD rows inside of user db that is not following anymore.
    #       The reason why we don't delete card on user db is, those cards can be used on another profile.
    task_cardsubscription_data = sqs_action.UserDBModifyData(
        'TB_CARD_SUBSCRIPTION',
        card_subscription.uuid,
        sqs_action.UserDBModifyActionCase.delete)
    sqs_action.UserDBModifyTaskMessage(
        card_subscription.profile.user_id,
        [task_cardsubscription_data, ]).add_to_queue()
