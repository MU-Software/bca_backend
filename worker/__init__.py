import celery
import pathlib as pt
import sys

sys.path.insert(0, pt.Path(__file__).parent.resolve().parent.as_posix())

import app.plugin.bca.user_db.celery_init as celery_init  # noqa

celery_app: celery.Celery = celery_init.init_celery_app()
