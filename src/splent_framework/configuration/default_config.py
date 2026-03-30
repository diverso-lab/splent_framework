import os


def _build_db_uri(db_name_env: str, db_name_default: str) -> str:
    return (
        f"mysql+pymysql://{os.getenv('MARIADB_USER', 'default_user')}:"
        f"{os.getenv('MARIADB_PASSWORD', 'default_password')}@"
        f"{os.getenv('MARIADB_HOSTNAME', 'localhost')}:3306/"
        f"{os.getenv(db_name_env, db_name_default)}"
    )


class Config:
    # WARNING: override SECRET_KEY via env var in all non-development environments
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_test_key_1234567890abcdefghijklmnopqrstu")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEMPLATES_AUTO_RELOAD = True
    UPLOAD_FOLDER = "uploads"
    # SESSION_TYPE is NOT set here — it must come from a session feature
    # (splent_feature_session_redis or splent_feature_session_filesystem)

    def __init__(self):
        # Resolved at instantiation time so runtime env changes are picked up
        self.TIMEZONE = os.getenv("TIMEZONE", "Europe/Madrid")


class DevelopmentConfig(Config):
    DEBUG = True

    def __init__(self):
        super().__init__()
        self.SQLALCHEMY_DATABASE_URI = _build_db_uri("MARIADB_DATABASE", "default_db")


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False

    def __init__(self):
        super().__init__()
        self.SQLALCHEMY_DATABASE_URI = _build_db_uri(
            "MARIADB_TEST_DATABASE", "default_test_db"
        )


class ProductionConfig(Config):
    DEBUG = False

    def __init__(self):
        super().__init__()
        if not os.getenv("SECRET_KEY"):
            raise RuntimeError(
                "SECRET_KEY environment variable must be set in production."
            )
        self.SQLALCHEMY_DATABASE_URI = _build_db_uri("MARIADB_DATABASE", "default_db")
