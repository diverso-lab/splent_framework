"""
Tests for BaseBlueprint.send_file — path traversal protection and normal serving.

We create a minimal Flask app, register a BaseBlueprint pointing to a temp
assets directory, and verify:
  - Legitimate files are served with correct MIME types
  - Subfolders outside the whitelist → 404
  - Filenames with path traversal sequences → 403
  - Non-existent files → 404
"""
import os
import pytest
from flask import Flask
from unittest.mock import patch, MagicMock

from splent_framework.blueprints.base_blueprint import BaseBlueprint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_asset_tree(base: str):
    """Create a small asset tree under base/assets/."""
    for subfolder in ("js", "css", "dist"):
        os.makedirs(os.path.join(base, "assets", subfolder), exist_ok=True)

    with open(os.path.join(base, "assets", "js", "app.js"), "w") as f:
        f.write("console.log('hello');")

    with open(os.path.join(base, "assets", "css", "style.css"), "w") as f:
        f.write("body { margin: 0; }")

    with open(os.path.join(base, "assets", "dist", "bundle.js"), "w") as f:
        f.write("// bundle")

    # A sensitive file outside assets (simulates a config file)
    with open(os.path.join(base, "secret.txt"), "w") as f:
        f.write("super secret")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def feature_dir(tmp_path):
    """Temp directory acting as a feature package root."""
    make_asset_tree(str(tmp_path))
    return tmp_path


@pytest.fixture
def app(feature_dir):
    """Flask test app with a BaseBlueprint wired to the temp feature dir."""
    application = Flask(__name__)
    application.config["TESTING"] = True
    application.config["SECRET_KEY"] = "test"

    # Patch the module resolution inside BaseBlueprint so it uses our temp dir
    fake_module = MagicMock()
    fake_module.__file__ = str(feature_dir / "__init__.py")

    with patch.dict("sys.modules", {"test_feature": fake_module}):
        bp = BaseBlueprint("test_feature", "test_feature")
        application.register_blueprint(bp)

    return application


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Serving legitimate files
# ---------------------------------------------------------------------------

class TestServeLegitimateFiles:
    def test_serves_js_with_correct_mimetype(self, client):
        resp = client.get("/test_feature/js/app.js")
        assert resp.status_code == 200
        assert "javascript" in resp.content_type

    def test_serves_css_with_correct_mimetype(self, client):
        resp = client.get("/test_feature/css/style.css")
        assert resp.status_code == 200
        assert "css" in resp.content_type

    def test_serves_dist_file(self, client):
        resp = client.get("/test_feature/dist/bundle.js")
        assert resp.status_code == 200

    def test_js_content_is_correct(self, client):
        resp = client.get("/test_feature/js/app.js")
        assert b"console.log" in resp.data


# ---------------------------------------------------------------------------
# Security: path traversal blocked
# ---------------------------------------------------------------------------

class TestPathTraversalBlocked:
    def test_traversal_in_filename_blocked(self, client):
        # Attempt to escape assets/js/ via ../
        resp = client.get("/test_feature/js/../../secret.txt")
        assert resp.status_code in (403, 404)

    def test_double_traversal_blocked(self, client):
        resp = client.get("/test_feature/js/../../../etc/passwd")
        assert resp.status_code in (403, 404)

    def test_encoded_traversal_blocked(self, client):
        resp = client.get("/test_feature/js/%2e%2e%2fsecret.txt")
        assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# Security: subfolder whitelist enforced
# ---------------------------------------------------------------------------

class TestSubfolderWhitelist:
    def test_invalid_subfolder_returns_404(self, client):
        resp = client.get("/test_feature/templates/base.html")
        assert resp.status_code == 404

    def test_uploads_subfolder_not_allowed(self, client):
        resp = client.get("/test_feature/uploads/malicious.py")
        assert resp.status_code == 404

    def test_empty_subfolder_not_allowed(self, client):
        resp = client.get("/test_feature//app.js")
        # Flask normalises double slashes, result must not be 200
        assert resp.status_code != 200


# ---------------------------------------------------------------------------
# Non-existent files
# ---------------------------------------------------------------------------

class TestNonExistentFiles:
    def test_missing_file_returns_404(self, client):
        resp = client.get("/test_feature/js/nonexistent.js")
        assert resp.status_code == 404

    def test_missing_css_returns_404(self, client):
        resp = client.get("/test_feature/css/missing.css")
        assert resp.status_code == 404
