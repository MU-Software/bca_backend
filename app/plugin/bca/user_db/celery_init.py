import celery
import flask
import typing

celery_app: celery.Celery = None
CeleryTask: typing.Type[celery.Task] = None


def init_celery_app():
    global celery_app
    global CeleryTask

    if celery_app is None:
        celery_backend_url = 'redis://'
        redis_password = flask.current_app.config.get('REDIS_PASSWORD', None)
        if redis_password:
            celery_backend_url += f':{redis_password}@'
        celery_backend_url += flask.current_app.config.get('REDIS_HOST') + ':'
        celery_backend_url += str(flask.current_app.config.get('REDIS_PORT'))
        celery_broker_url = celery_backend_url

        celery_app = celery.Celery(
            main='userdbmod1',
            backend=celery_backend_url,
            broker=celery_broker_url)
        celery_app.conf.update(flask.current_app.config)
        celery_app.conf.task_ignore_result = True

        class ContextTask(celery_app.Task):
            def __call__(self, *args, **kwargs):
                with flask.current_app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = CeleryTask = ContextTask

    return celery_app
