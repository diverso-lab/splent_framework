"""
Tests for FeatureEntryParser and FeatureRef.

Covers all supported entry formats:
  org/name@version  |  name@version  |  org/name  |  name
"""
import pytest
from splent_framework.managers.feature_loader import FeatureEntryParser, FeatureRef, FeatureError


@pytest.fixture
def parser():
    return FeatureEntryParser()


class TestParseFeatureEntryFormats:
    def test_full_format_org_name_version(self, parser):
        ref = parser.parse("splent-io/splent_feature_auth@v1.1.0")
        assert ref.org == "splent-io"
        assert ref.org_safe == "splent_io"
        assert ref.name == "splent_feature_auth"
        assert ref.version == "v1.1.0"

    def test_name_only_defaults_to_splent_io_org(self, parser):
        ref = parser.parse("splent_feature_auth")
        assert ref.org == "splent-io"
        assert ref.org_safe == "splent_io"
        assert ref.name == "splent_feature_auth"
        assert ref.version is None

    def test_name_with_version_no_org(self, parser):
        ref = parser.parse("splent_feature_auth@v2.0.0")
        assert ref.org == "splent-io"
        assert ref.name == "splent_feature_auth"
        assert ref.version == "v2.0.0"

    def test_org_and_name_without_version(self, parser):
        ref = parser.parse("my-org/my_feature")
        assert ref.org == "my-org"
        assert ref.org_safe == "my_org"
        assert ref.name == "my_feature"
        assert ref.version is None

    def test_org_with_dashes_converted_to_underscores(self, parser):
        ref = parser.parse("my-cool-org/some_feature@v1.0.0")
        assert ref.org_safe == "my_cool_org"
        assert ref.org == "my-cool-org"

    def test_import_name_combines_org_safe_and_name(self, parser):
        ref = parser.parse("splent-io/splent_feature_auth@v1.0.0")
        assert ref.import_name() == "splent_io.splent_feature_auth"

    def test_import_name_for_custom_org(self, parser):
        ref = parser.parse("my-org/my_feature")
        assert ref.import_name() == "my_org.my_feature"


class TestParseFeatureEntryValidation:
    def test_raises_on_empty_name_after_slash(self, parser):
        with pytest.raises(FeatureError, match="Invalid feature entry"):
            parser.parse("splent-io/@v1.0.0")

    def test_raises_on_completely_empty_string(self, parser):
        with pytest.raises(FeatureError):
            parser.parse("")


class TestFeatureRefImmutability:
    def test_feature_ref_is_frozen(self, parser):
        ref = parser.parse("splent-io/splent_feature_auth@v1.0.0")
        with pytest.raises((AttributeError, TypeError)):
            ref.name = "something_else"  # type: ignore[misc]

    def test_feature_ref_equality(self, parser):
        ref1 = parser.parse("splent-io/splent_feature_auth@v1.0.0")
        ref2 = parser.parse("splent-io/splent_feature_auth@v1.0.0")
        assert ref1 == ref2

    def test_different_versions_not_equal(self, parser):
        ref1 = parser.parse("splent-io/splent_feature_auth@v1.0.0")
        ref2 = parser.parse("splent-io/splent_feature_auth@v2.0.0")
        assert ref1 != ref2
