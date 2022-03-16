import celery
import os

internal_celery_app: celery.Celery = None


def init_celery_app():
    global internal_celery_app

    if internal_celery_app is None:
        celery_backend_url = 'redis://'
        redis_password = os.environ.get('REDIS_PASSWORD', None)
        if redis_password:
            celery_backend_url += f':{redis_password}@'
        celery_backend_url += os.environ.get('REDIS_HOST') + ':'
        celery_backend_url += str(os.environ.get('REDIS_PORT'))
        celery_broker_url = celery_backend_url

        internal_celery_app = celery.Celery(
            main='userdbmod1',
            backend=celery_backend_url,
            broker=celery_broker_url)
        internal_celery_app.conf.task_ignore_result = True

        import app.plugin.bca.user_db.journal_handler as journal_handler  # noqa

    return internal_celery_app


init_celery_app()
