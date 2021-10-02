import app.api.bca.profile as profile_route_collection
import app.api.bca.card as card_route_collection
import app.api.bca.chat as chat_route_collection
import app.api.bca.sync as sync_route_collection

bca_resource_route = dict()
bca_resource_route.update(profile_route_collection.resource_route)
bca_resource_route.update(card_route_collection.resource_route)
bca_resource_route.update(chat_route_collection.resource_route)
bca_resource_route.update(sync_route_collection.resource_route)
