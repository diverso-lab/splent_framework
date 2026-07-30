import os


def _build_db_uri(db_name_env: str, db_name_default: str) -> str:
    return (
        f"mysql+pymysql://{os.getenv('MARIADB_USER', 'default_user')}:"
        f"{os.getenv('MARIADB_PASSWORD', 'default_password')}@"
        f"{os.getenv('MARIADB_HOSTNAME', 'localhost')}:3306/"
        f"{os.getenv(db_name_env, db_name_default)}"
    )


def _locales(raw: str, default: str) -> list[str]:
    """The languages a product offers, from a comma separated list.

    The default locale is always among them, first, so a product that names
    a default and forgets the list still works and the language it says it
    speaks is the one it falls back to. Order is kept as written, because a
    switcher renders it in that order and the first is the one a reader who
    asked for nothing gets.
    """
    codes = [code.strip() for code in (raw or "").split(",") if code.strip()]
    if default and default not in codes:
        codes.insert(0, default)
    return codes or ["en"]


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

        # What language the product speaks. LocaleManager has always read
        # these from app.config and nothing ever put them there, so every
        # product answered in English no matter what its .env said, and the
        # theme's language switcher never appeared because it only shows
        # with more than one locale. The language a wiki is taught in is
        # configuration of the product, not of a feature, so it belongs
        # here next to the timezone.
        self.BABEL_DEFAULT_LOCALE = os.getenv("BABEL_DEFAULT_LOCALE", "en").strip()
        self.BABEL_SUPPORTED_LOCALES = _locales(
            os.getenv("BABEL_SUPPORTED_LOCALES", ""), self.BABEL_DEFAULT_LOCALE
        )
        # Whether a reader's browser gets to override the language above.
        # Off by default: a site built for an institution speaks that
        # institution's language, and the switcher is how a reader asks for
        # another one.
        self.BABEL_NEGOTIATE_FROM_HEADER = os.getenv(
            "BABEL_NEGOTIATE_FROM_HEADER", ""
        ).strip().lower() in {"1", "true", "yes", "on"}


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
