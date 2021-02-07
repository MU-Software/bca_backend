import os
import secrets


class Config:
    DEBUG = False
    TESTING = False

    JSON_AS_ASCII = False
    PROJECT_NAME = os.environ.get('PROJECT_NAME')
    BACKEND_NAME = os.environ.get('BACKEND_NAME')
    SERVER_NAME = os.environ.get('SERVER_NAME', None)

    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))

    RESTAPI_VERSION = os.environ.get('RESTAPI_VERSION')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DB_URL')

    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
    REDIS_HOST = os.environ.get('REDIS_HOST')
    REDIS_PORT = int(os.environ.get('REDIS_PORT'))
    REDIS_DB = int(os.environ.get('REDIS_DB'))

    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    GOOGLE_REFRESH_TOKEN = os.environ.get('GOOGLE_REFRESH_TOKEN')


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    # os.environ['AUTHLIB_INSECURE_TRANSPORT'] = True

    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DB_URL', 'sqlite:///:memory:')
    # SQLALCHEMY_BINDS = {  # Use this when multiple DB connections are needed
    #     'default': SQLALCHEMY_DATABASE_URI,
    # }

    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_DB = int(os.environ.get('REDIS_DB', 0))


class TestingConfig(Config):
    DEBUG = False
    TESTING = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


config_by_name = dict(
    development=DevelopmentConfig,
    testing=TestingConfig,
    production=ProductionConfig,
)
