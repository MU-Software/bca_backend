import boto3
import botocore
import flask
import flask_admin as fadmin

import app.common.utils as utils
import app.api.helper_class as api_class

from app.api.response_case import CommonResponseCase


class Admin_UserDBFlush_View(fadmin.BaseView):
    @fadmin.expose('/', methods=('GET',))
    def index(self):
        restapi_version = flask.current_app.config.get('RESTAPI_VERSION')

        return self.render(
            'admin/userdb_flush.html',
            restapi_version=restapi_version)

    @fadmin.expose('/', methods=('POST',))
    @api_class.RequestBody(
        required_fields={},
        optional_fields={
            'flushUserDB': {'type': 'boolean', },
            'flushTaskQueue': {'type': 'boolean', },
        })
    def post(self, req_body: dict):
        restapi_version = flask.current_app.config.get('RESTAPI_VERSION')

        if not any((('flushUserDB' in req_body), ('flushTaskQueue' in req_body))):
            CommonResponseCase.body_required_omitted.create_response(
                message='Need flushUserDB or flushTaskQueue',
                data={'lacks': ['flushUserDB', 'flushTaskQueue']})

        if 'flushUserDB' in req_body:
            try:
                bucket_name = flask.current_app.config.get('AWS_S3_BUCKET_NAME')
                s3 = boto3.client('s3', region_name=flask.current_app.config.get('AWS_REGION'))
                file_list = [{'Key': file['Key']} for file in s3.list_objects(
                    Bucket=bucket_name,
                    Prefix='user_db')['Contents']]
                s3.delete_objects(Bucket=bucket_name, Delete={'Objects': file_list, })
            except botocore.client.ClientError as err:
                if utils.safe_int(err.response['Error']['Code']) == 404:
                    return
                print(utils.get_traceback_msg(err))
                raise err
            except Exception as err:
                print(utils.get_traceback_msg(err))
                raise err

        else:  # if flushTaskQueue
            try:
                task_sqs_url = flask.current_app.config.get('AWS_TASK_SQS_URL')
                sqs = boto3.client('sqs', region_name=flask.current_app.config.get('AWS_REGION'))
                sqs.purge_queue(QueueUrl=task_sqs_url)
            except botocore.client.ClientError as err:
                print(utils.get_traceback_msg(err))
                raise err
            except Exception as err:
                print(utils.get_traceback_msg(err))
                raise err

        return CommonResponseCase.http_ok.create_response(
            code=301,
            header=(('Location', f'/api/{restapi_version}/admin/userdb-flush'), ))
