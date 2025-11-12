import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_test_key_1234567890abcdefghijklmnopqrstu")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TIMEZONE = "Europe/Madrid"
    TEMPLATES_AUTO_RELOAD = True
    UPLOAD_FOLDER = "uploads"
    SESSION_TYPE = "filesystem"

    def __init__(self):
        pass


class DevelopmentConfig(Config):
    DEBUG = True

    def __init__(self):
        super().__init__()
        self.SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{os.getenv('MARIADB_USER', 'default_user')}:"
            f"{os.getenv('MARIADB_PASSWORD', 'default_password')}@"
            f"{os.getenv('MARIADB_HOSTNAME', 'localhost')}:3306/"
            f"{os.getenv('MARIADB_DATABASE', 'default_db')}"
        )


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SESSION_TYPE = "filesystem"
    SESSION_FILE_DIR = "/tmp/flask_sessions"

    def __init__(self):
        super().__init__()
        self.SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{os.getenv('MARIADB_USER', 'default_user')}:"
            f"{os.getenv('MARIADB_PASSWORD', 'default_password')}@"
            f"{os.getenv('MARIADB_HOSTNAME', 'localhost')}:3306/"
            f"{os.getenv('MARIADB_TEST_DATABASE', 'default_test_db')}"
        )


class ProductionConfig(Config):
    DEBUG = False

    def __init__(self):
        super().__init__()
        self.SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{os.getenv('MARIADB_USER', 'default_user')}:"
            f"{os.getenv('MARIADB_PASSWORD', 'default_password')}@"
            f"{os.getenv('MARIADB_HOSTNAME', 'localhost')}:3306/"
            f"{os.getenv('MARIADB_DATABASE', 'default_db')}"
        )
