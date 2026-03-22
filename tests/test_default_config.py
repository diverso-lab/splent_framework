"""
Tests for splent_framework.configuration.default_config

Covers:
- _build_db_uri(): URI construction from env vars
- DevelopmentConfig: DEBUG=True, picks MARIADB_DATABASE
- TestingConfig: TESTING=True, picks MARIADB_TEST_DATABASE
- ProductionConfig: DEBUG=False, picks MARIADB_DATABASE
- Config base: SECRET_KEY, static class attributes
"""
import pytest
from splent_framework.configuration.default_config import (
    _build_db_uri,
    Config,
    DevelopmentConfig,
    TestingConfig,
    ProductionConfig,
)


class TestBuildDbUri:
    def test_uses_env_vars(self, monkeypatch):
        monkeypatch.setenv("MARIADB_USER", "myuser")
        monkeypatch.setenv("MARIADB_PASSWORD", "mypass")
        monkeypatch.setenv("MARIADB_HOSTNAME", "myhost")
        monkeypatch.setenv("MY_DB", "mydb")

        uri = _build_db_uri("MY_DB", "fallback_db")

        assert uri == "mysql+pymysql://myuser:mypass@myhost:3306/mydb"

    def test_falls_back_to_default_when_env_missing(self, monkeypatch):
        monkeypatch.delenv("MARIADB_USER", raising=False)
        monkeypatch.delenv("MARIADB_PASSWORD", raising=False)
        monkeypatch.delenv("MARIADB_HOSTNAME", raising=False)
        monkeypatch.delenv("MISSING_DB_VAR", raising=False)

        uri = _build_db_uri("MISSING_DB_VAR", "fallback_db")

        assert "fallback_db" in uri
        assert "mysql+pymysql://" in uri

    def test_hostname_used_in_uri(self, monkeypatch):
        monkeypatch.setenv("MARIADB_HOSTNAME", "db.internal")
        monkeypatch.setenv("TEST_DB", "mydb")

        uri = _build_db_uri("TEST_DB", "x")

        assert "db.internal:3306" in uri

    def test_database_name_at_end_of_uri(self, monkeypatch):
        monkeypatch.setenv("MY_DB_NAME", "orders_db")

        uri = _build_db_uri("MY_DB_NAME", "fallback")

        assert uri.endswith("/orders_db")

    def test_different_db_env_vars_produce_different_uris(self, monkeypatch):
        monkeypatch.setenv("DB_ONE", "db_one")
        monkeypatch.setenv("DB_TWO", "db_two")

        assert _build_db_uri("DB_ONE", "x") != _build_db_uri("DB_TWO", "x")


class TestConfig:
    def test_has_secret_key(self):
        assert Config.SECRET_KEY is not None
        assert len(Config.SECRET_KEY) > 0

    def test_track_modifications_disabled(self):
        assert Config.SQLALCHEMY_TRACK_MODIFICATIONS is False

    def test_session_type_filesystem(self):
        assert Config.SESSION_TYPE == "filesystem"

    def test_templates_auto_reload(self):
        assert Config.TEMPLATES_AUTO_RELOAD is True


class TestDevelopmentConfig:
    def test_debug_is_true(self):
        assert DevelopmentConfig.DEBUG is True

    def test_database_uri_present(self, monkeypatch):
        monkeypatch.setenv("MARIADB_DATABASE", "dev_db")
        cfg = DevelopmentConfig()
        assert "dev_db" in cfg.SQLALCHEMY_DATABASE_URI

    def test_database_uri_uses_mariadb_database_not_test(self, monkeypatch):
        monkeypatch.setenv("MARIADB_DATABASE", "prod_like_db")
        monkeypatch.setenv("MARIADB_TEST_DATABASE", "test_db")
        cfg = DevelopmentConfig()
        assert "prod_like_db" in cfg.SQLALCHEMY_DATABASE_URI
        assert "test_db" not in cfg.SQLALCHEMY_DATABASE_URI


class TestTestingConfig:
    def test_testing_is_true(self):
        assert TestingConfig.TESTING is True

    def test_csrf_disabled(self):
        assert TestingConfig.WTF_CSRF_ENABLED is False

    def test_uses_test_database(self, monkeypatch):
        monkeypatch.setenv("MARIADB_TEST_DATABASE", "my_test_db")
        cfg = TestingConfig()
        assert "my_test_db" in cfg.SQLALCHEMY_DATABASE_URI

    def test_does_not_use_production_database(self, monkeypatch):
        monkeypatch.setenv("MARIADB_DATABASE", "prod_db")
        monkeypatch.setenv("MARIADB_TEST_DATABASE", "test_db")
        cfg = TestingConfig()
        assert "prod_db" not in cfg.SQLALCHEMY_DATABASE_URI

    def test_session_file_dir(self):
        cfg = TestingConfig()
        assert cfg.SESSION_FILE_DIR == "/tmp/flask_sessions"


class TestProductionConfig:
    def test_debug_is_false(self):
        assert ProductionConfig.DEBUG is False

    def test_raises_without_secret_key(self, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            ProductionConfig()

    def test_database_uri_present(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "a-real-secret")
        monkeypatch.setenv("MARIADB_DATABASE", "prod_db")
        cfg = ProductionConfig()
        assert "prod_db" in cfg.SQLALCHEMY_DATABASE_URI

    def test_uses_mariadb_database_not_test(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "a-real-secret")
        monkeypatch.setenv("MARIADB_DATABASE", "prod_db")
        monkeypatch.setenv("MARIADB_TEST_DATABASE", "test_db")
        cfg = ProductionConfig()
        assert "test_db" not in cfg.SQLALCHEMY_DATABASE_URI
