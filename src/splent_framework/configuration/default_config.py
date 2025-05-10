import os
import redis


class Config:
    SECRET_KEY = os.getenv(
        "SECRET_KEY", "dev_test_key_1234567890abcdefghijklmnopqrstu"
    )
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{os.getenv('MARIADB_USER', 'default_user')}:"
        f"{os.getenv('MARIADB_PASSWORD', 'default_password')}@"
        f"{os.getenv('MARIADB_HOSTNAME', 'localhost')}:"
        f"{'3306'}/"
        f"{os.getenv('MARIADB_DATABASE', 'default_db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TIMEZONE = "Europe/Madrid"
    TEMPLATES_AUTO_RELOAD = True
    UPLOAD_FOLDER = "uploads"
    SESSION_TYPE = "redis"
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
    SESSION_REDIS = redis.from_url(REDIS_URL)
    REDIS_WORKER_TIMEOUT = os.getenv("REDIS_WORKER_TIMEOUT", 180)


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{os.getenv('MARIADB_USER', 'default_user')}:"
        f"{os.getenv('MARIADB_PASSWORD', 'default_password')}@"
        f"{os.getenv('MARIADB_HOSTNAME', 'localhost')}:"
        f"{'3306'}/"
        f"{os.getenv('MARIADB_TEST_DATABASE', 'default_db')}"
    )
    WTF_CSRF_ENABLED = False
    SESSION_TYPE = "filesystem"
    SESSION_FILE_DIR = "/tmp/flask_sessions"


class ProductionConfig(Config):
    DEBUG = False
