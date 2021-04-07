import apispec
import click
import flask
import flask.cli
import pathlib as pt
import re
import typing
import werkzeug.routing
import yaml

import app.api.helper_class as api_class

RE_URL = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")
PATH_PARAM_URL = re.compile(r"<([^:<>]+):?([^<>]+)>")

routes_cache: dict[str, tuple[str, typing.Any]] = dict()
response_cases_cache: dict[str, api_class.Response] = dict()


# FROST was the original name of this project.
class FrostRoutePlugin(apispec.BasePlugin):
    def path_helper(self, path: str, operations: typing.OrderedDict, *, view, app: flask.Flask = None, **kwargs):
        app: flask.Flask = app or flask.current_app
        operation_result = dict()
        http_mtd: dict[str, typing.Any] = {k: v for k, v in view.__dict__.items() if k in api_class.http_all_method}

        path_params_data: list[dict] = list()
        # Add path parameters on doc
        if '{' in path:
            orig_path: str = routes_cache[path][0]
            path_params: list[tuple[str, str]] = PATH_PARAM_URL.findall(orig_path)
            for path_param in path_params:
                path_params_data.append({
                    'in': 'path',
                    'name': path_param[1],
                    'required': True,
                    'schema': {
                        'type': path_param[0],
                    },
                })

        for mtd_name, mtd_func in http_mtd.items():
            print(mtd_func)
            if not mtd_func.__doc__:
                raise Exception(f'No docstring on {view.__name__}.{mtd_name}')

            document: dict[str, typing.Any] = yaml.safe_load(mtd_func.__doc__)
            doc_resps: list[str] = document.pop('responses')
            openapi_resp: dict = dict()
            for resp in doc_resps:
                resp_case_obj: api_class.Response = response_cases_cache[resp]
                if resp_case_obj.code not in openapi_resp:
                    openapi_resp[resp_case_obj.code] = {
                        'description': '',
                        'content': {
                            'application/json': {
                                'schema': {
                                    'oneOf': [

                                    ]
                                }
                            }
                        }
                    }
                openapi_resp[resp_case_obj.code]['content']['application/json']['schema']['oneOf'].append(
                    {'$ref': f'#/components/schemas/{resp}'}
                )
                openapi_resp[resp_case_obj.code]['description'] += f'### {resp}: {resp_case_obj.description}  \n'
            document['responses'] = openapi_resp

            if path_params_data:
                if 'parameters' not in document:
                    document['parameters'] = path_params_data
                else:
                    document['parameters'] += path_params_data

            operation_result[mtd_name] = document
        operations.update(operation_result)


@click.command('create-openapi-doc')
@flask.cli.with_appcontext
def create_openapi_doc():
    project_name: str = flask.current_app.config.get('PROJECT_NAME')
    restapi_version: str = flask.current_app.config.get('RESTAPI_VERSION')

    spec = apispec.APISpec(
        title=f'{project_name} RESTful API',
        version=flask.current_app.config.get('RESTAPI_VERSION'),
        info={
            'description': f'{project_name} API 명세 문서입니다.',
        },
        openapi_version='3.0.3',
        plugins=(FrostRoutePlugin(),),
    )

    # Register all possible response cases on components.schema
    for response_case_collection in api_class.ResponseCaseCollector._subclasses:
        response_cases: dict[str, api_class.Response] = {k: v for k, v in response_case_collection.__dict__.items()
                                                         if not k.startswith('_')}

        for resp_case_name, resp_case_obj in response_cases.items():
            response_cases_cache[resp_case_name] = resp_case_obj
            spec.components.schema(
                name=resp_case_name,
                component={
                    'type': 'object',
                    'properties': resp_case_obj.to_openapi_obj(),
                }
            )

    # Register all routes
    route_classes: dict = {cls.__name__: cls for cls in api_class.MethodViewMixin._subclasses}
    rule: werkzeug.routing.Rule
    for rule in flask.current_app.url_map.iter_rules():
        route_path: str = RE_URL.sub(r"{\1}", str(rule))
        route_path_split: list = [z for z in route_path.split('/') if z]

        if route_path_split[0] == restapi_version and route_path_split[1] != 'debug':
            route_view_class = route_classes[rule.endpoint]
            # for method in rule.methods:
            routes_cache[route_path] = (str(rule), route_view_class)
            spec.path(path=route_path, view=route_view_class)

    doc_file: pt.Path = pt.Path('doc/openapi3.yaml')
    if doc_file.exists():
        doc_file.unlink()

    with doc_file.open('w') as fp:
        fp.write(spec.to_yaml())
