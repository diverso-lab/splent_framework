"""A feature that cannot import must say so, not go quiet.

The loader imports each feature's conventional submodules and ignores the
ones a feature does not have. ModuleNotFoundError was doing double duty
there: it is raised both when routes.py is absent, which is normal, and
when routes.py is present and imports a package nobody installed, which is
a broken feature. Treating the second as the first left the feature
registered and mute, its blueprint present, its asset route working and
every page it owned answering 404, with nothing in the log.

That happened twice with the same feature and the same missing package, so
it is pinned here.
"""

import sys
import types

import pytest

from splent_framework.managers.feature_loader import FeatureError, FeatureImporter


@pytest.fixture
def importer():
    return FeatureImporter()


@pytest.fixture
def fake_feature():
    """A package whose routes module imports something that is not there."""
    package = types.ModuleType("fake_feature")
    package.__path__ = []
    sys.modules["fake_feature"] = package
    yield "fake_feature"
    for name in list(sys.modules):
        if name.startswith("fake_feature"):
            del sys.modules[name]


class TestAMissingSubmoduleIsFine:
    def test_a_feature_without_that_submodule_is_skipped(self, importer, fake_feature):
        """Most features have no signals.py, and that is not an error."""
        importer._try_import(fake_feature, "signals")


class TestAMissingDependencyIsNot:
    def test_it_says_which_package_is_missing(
        self, importer, fake_feature, monkeypatch
    ):
        def explode(name):
            raise ModuleNotFoundError(
                "No module named 'mdit_py_plugins'", name="mdit_py_plugins"
            )

        monkeypatch.setattr(
            "splent_framework.managers.feature_loader.importlib.import_module", explode
        )

        with pytest.raises(FeatureError) as raised:
            importer._try_import(fake_feature, "routes")

        message = str(raised.value)
        assert "mdit_py_plugins" in message
        assert "fake_feature.routes" in message

    def test_any_other_import_error_still_stops_the_load(
        self, importer, fake_feature, monkeypatch
    ):
        def explode(name):
            raise ValueError("the module raised while being imported")

        monkeypatch.setattr(
            "splent_framework.managers.feature_loader.importlib.import_module", explode
        )

        with pytest.raises(FeatureError):
            importer._try_import(fake_feature, "routes")
