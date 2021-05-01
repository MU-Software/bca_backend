import os
import secrets


class Config:
    DEBUG = False
    TESTING = False
    SERVER_IS_ON_PROXY = bool(os.environ.get('SERVER_IS_ON_PROXY', False))

    JSON_AS_ASCII = False
    PROJECT_NAME = os.environ.get('PROJECT_NAME')
    BACKEND_NAME = os.environ.get('BACKEND_NAME')
    SERVER_NAME = os.environ.get('SERVER_NAME', None)

    # Referer is not a typo. See HTTP referer header.
    # This will enable only if $env:REFERER_CHECK is 'false'
    REFERER_CHECK = os.environ.get('REFERER_CHECK', True) != 'false'
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    DEVELOPMENT_KEY = os.environ.get('DEVELOPMENT_KEY')
    LOCAL_DEV_CLIENT_PORT = None

    RESTAPI_VERSION = os.environ.get('RESTAPI_VERSION')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DB_URL')

    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
    REDIS_HOST = os.environ.get('REDIS_HOST')
    REDIS_PORT = int(os.environ.get('REDIS_PORT'))
    REDIS_DB = int(os.environ.get('REDIS_DB'))

    # This will enable only if $env:MAIL_ENABLE is 'false'
    MAIL_ENABLE = os.environ.get('MAIL_ENABLE', True) != 'false'
    MAIL_DOMAIN = os.environ.get('MAIL_DOMAIN', None)

    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', None)
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', None)
    GOOGLE_REFRESH_TOKEN = os.environ.get('GOOGLE_REFRESH_TOKEN', None)

    AWS_REGION = os.environ.get('AWS_REGION', 'ap-northeast-2')  # Default set to Seoul, Korea (of course, south!)
    AWS_S3_BUCKET_NAME = os.environ.get('AWS_S3_BUCKET_NAME', None)


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

    LOCAL_DEV_CLIENT_PORT = int(os.environ.get('LOCAL_DEV_CLIENT_PORT'))\
        if os.environ.get('LOCAL_DEV_CLIENT_PORT') else None


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
