import boto3
import click
import flask
import flask.cli

import app.common.utils as utils
import app.database


@click.command('reset-bca')
@flask.cli.with_appcontext
def drop_db():
    restapi_ver = flask.current_app.config.get('RESTAPI_VERSION', 'prod')
    region_name = flask.current_app.config.get('AWS_REGION')
    bucket_name = flask.current_app.config.get('AWS_S3_BUCKET_NAME')
    task_sqs_url = flask.current_app.config.get('AWS_TASK_SQS_URL')

    if restapi_ver != 'dev':
        print('Cannot reset BCa Service: RESTAPI_VERSION is not \'dev\'')
        return

    try:
        app.database.db.drop_all()
        print('Successfully dropped DB')
    except Exception as err:
        print(utils.get_traceback_msg(err))
        print('Error raised while dropping DB')

    try:
        app.database.redis_db.flushdb()
        print('Successfully dropped Redis DB')
    except Exception as err:
        print(utils.get_traceback_msg(err))
        print('Error raised while dropping Redis DB')

    try:
        s3 = boto3.client('s3', region_name=region_name)
        file_list = [{'Key': file['Key']} for file in s3.list_objects(
            Bucket=bucket_name,
            Prefix='user_db')['Contents']]
        s3.delete_objects(Bucket=bucket_name, Delete={'Objects': file_list, })
        print('Successfully deleted all user\'s DB')
    except Exception as err:
        print(utils.get_traceback_msg(err))
        print('Error raised while deleting user DB')

    try:
        sqs = boto3.client('sqs', region_name=region_name)
        sqs.purge_queue(QueueUrl=task_sqs_url)
        print('Successfully purged Task SQS')
    except Exception as err:
        print(utils.get_traceback_msg(err))
        print('Error raised while purging Task SQS')
