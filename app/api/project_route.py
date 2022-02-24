# Import and add project routes here.
# If you want to make git not to track this file anymore,
# use `git update-index --skip-worktree app/api/project_route.py`
import app.api.bca as bca_route

project_resource_routes = dict()
project_resource_routes.update(bca_route.bca_resource_route)
