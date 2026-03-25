"""
Tests for FeatureLoadOrderResolver.

Validates the topological sort algorithm against the UVL constraint model:
  - profile => auth         (profile requires auth)
  - confirmemail => mail    (confirmemail requires mail)
  - reset => mail           (reset requires mail)

All test cases use realistic pyproject-style feature entries.
"""

import pytest
from splent_framework.managers.feature_order import FeatureLoadOrderResolver
from splent_framework.managers.feature_loader import FeatureError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RESOLVER = FeatureLoadOrderResolver()

# Minimal UVL that mirrors sample_splent_app/uvl/sample_splent_app.uvl
SAMPLE_UVL = """\
features
\tsample_splent_app
\t\tmandatory
\t\t\tauth {org 'splent-io', package 'splent_feature_auth'}
\t\tmandatory
\t\t\tpublic {org 'splent-io', package 'splent_feature_public'}
\t\toptional
\t\t\tmail {org 'splent-io', package 'splent_feature_mail'}
\t\toptional
\t\t\tconfirmemail {org 'splent-io', package 'splent_feature_confirmemail'}
\t\toptional
\t\t\tprofile {org 'splent-io', package 'splent_feature_profile'}
\t\toptional
\t\t\treset {org 'splent-io', package 'splent_feature_reset'}
constraints
\tprofile => auth
\tconfirmemail => mail
\treset => mail
"""

CYCLIC_UVL = """\
features
\tapp
\t\toptional
\t\t\ta {package 'feature_a'}
\t\toptional
\t\t\tb {package 'feature_b'}
constraints
\ta => b
\tb => a
"""


def write_uvl(tmp_path, content: str) -> str:
    p = tmp_path / "test.uvl"
    p.write_text(content)
    return str(p)


def pkg(name: str) -> str:
    """Build a realistic pyproject feature entry."""
    return f"splent_feature_{name}@v1.0.0"


# ---------------------------------------------------------------------------
# UVL parsing
# ---------------------------------------------------------------------------

class TestParsePackageMap:
    def test_extracts_short_to_package_mapping(self):
        mapping = FeatureLoadOrderResolver._parse_package_map(SAMPLE_UVL)
        assert mapping["auth"] == "splent_feature_auth"
        assert mapping["profile"] == "splent_feature_profile"
        assert mapping["mail"] == "splent_feature_mail"

    def test_returns_empty_for_no_attributes(self):
        assert FeatureLoadOrderResolver._parse_package_map("features\n\tapp\n") == {}


class TestParseConstraints:
    def test_extracts_implication_pairs(self):
        constraints = FeatureLoadOrderResolver._parse_constraints(SAMPLE_UVL)
        assert ("profile", "auth") in constraints
        assert ("confirmemail", "mail") in constraints
        assert ("reset", "mail") in constraints

    def test_ignores_non_constraint_lines(self):
        text = "features\n\tapp\n\t\toptional\n\t\t\tauth {package 'splent_feature_auth'}\n"
        assert FeatureLoadOrderResolver._parse_constraints(text) == []

    def test_ignores_comment_lines(self):
        text = "constraints\n\t// profile => auth\n\tprofile => auth\n"
        result = FeatureLoadOrderResolver._parse_constraints(text)
        assert result == [("profile", "auth")]


# ---------------------------------------------------------------------------
# Core ordering — single constraint
# ---------------------------------------------------------------------------

class TestSingleDependency:
    def test_profile_loads_after_auth_when_profile_declared_first(self, tmp_path):
        uvl = write_uvl(tmp_path, SAMPLE_UVL)
        features = [pkg("profile"), pkg("auth")]
        result = RESOLVER.resolve(features, uvl)
        assert result.index(pkg("auth")) < result.index(pkg("profile"))

    def test_already_correct_order_is_unchanged(self, tmp_path):
        uvl = write_uvl(tmp_path, SAMPLE_UVL)
        features = [pkg("auth"), pkg("profile")]
        result = RESOLVER.resolve(features, uvl)
        assert result == [pkg("auth"), pkg("profile")]

    def test_confirmemail_loads_after_mail(self, tmp_path):
        uvl = write_uvl(tmp_path, SAMPLE_UVL)
        features = [pkg("confirmemail"), pkg("mail")]
        result = RESOLVER.resolve(features, uvl)
        assert result.index(pkg("mail")) < result.index(pkg("confirmemail"))

    def test_reset_loads_after_mail(self, tmp_path):
        uvl = write_uvl(tmp_path, SAMPLE_UVL)
        features = [pkg("reset"), pkg("mail")]
        result = RESOLVER.resolve(features, uvl)
        assert result.index(pkg("mail")) < result.index(pkg("reset"))


# ---------------------------------------------------------------------------
# Full product set (mirrors sample_splent_app)
# ---------------------------------------------------------------------------

class TestFullProductOrder:
    FULL = [
        pkg("profile"),
        pkg("auth"),
        pkg("public"),
        pkg("confirmemail"),
        pkg("mail"),
        pkg("reset"),
    ]

    def test_auth_before_profile(self, tmp_path):
        uvl = write_uvl(tmp_path, SAMPLE_UVL)
        result = RESOLVER.resolve(self.FULL, uvl)
        assert result.index(pkg("auth")) < result.index(pkg("profile"))

    def test_mail_before_confirmemail(self, tmp_path):
        uvl = write_uvl(tmp_path, SAMPLE_UVL)
        result = RESOLVER.resolve(self.FULL, uvl)
        assert result.index(pkg("mail")) < result.index(pkg("confirmemail"))

    def test_mail_before_reset(self, tmp_path):
        uvl = write_uvl(tmp_path, SAMPLE_UVL)
        result = RESOLVER.resolve(self.FULL, uvl)
        assert result.index(pkg("mail")) < result.index(pkg("reset"))

    def test_all_features_present_in_result(self, tmp_path):
        uvl = write_uvl(tmp_path, SAMPLE_UVL)
        result = RESOLVER.resolve(self.FULL, uvl)
        assert sorted(result) == sorted(self.FULL)

    def test_independent_features_preserve_relative_order(self, tmp_path):
        """auth and public have no constraint between them — original order kept."""
        uvl = write_uvl(tmp_path, SAMPLE_UVL)
        result = RESOLVER.resolve(self.FULL, uvl)
        # auth appears before public in FULL and has no dependency on public
        assert result.index(pkg("auth")) < result.index(pkg("public"))


# ---------------------------------------------------------------------------
# Fallback behaviour
# ---------------------------------------------------------------------------

class TestFallback:
    def test_returns_original_order_when_uvl_path_is_none(self):
        features = [pkg("profile"), pkg("auth")]
        result = RESOLVER.resolve(features, None)
        assert result == features

    def test_returns_original_order_when_uvl_file_missing(self, tmp_path):
        features = [pkg("profile"), pkg("auth")]
        result = RESOLVER.resolve(features, str(tmp_path / "nonexistent.uvl"))
        assert result == features

    def test_returns_original_order_when_no_constraints_apply(self, tmp_path):
        """Features not mentioned in UVL constraints → pyproject order."""
        uvl = write_uvl(tmp_path, SAMPLE_UVL)
        features = [pkg("public"), pkg("redis")]   # neither in UVL constraints
        result = RESOLVER.resolve(features, uvl)
        assert result == features

    def test_returns_empty_list_unchanged(self, tmp_path):
        uvl = write_uvl(tmp_path, SAMPLE_UVL)
        assert RESOLVER.resolve([], uvl) == []


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

class TestCycleDetection:
    def test_raises_on_direct_cycle(self, tmp_path):
        uvl = write_uvl(tmp_path, CYCLIC_UVL)
        features = ["feature_a@v1.0.0", "feature_b@v1.0.0"]
        with pytest.raises(FeatureError, match="Circular dependency"):
            RESOLVER.resolve(features, uvl)

    def test_error_message_names_involved_features(self, tmp_path):
        uvl = write_uvl(tmp_path, CYCLIC_UVL)
        features = ["feature_a@v1.0.0", "feature_b@v1.0.0"]
        with pytest.raises(FeatureError) as exc_info:
            RESOLVER.resolve(features, uvl)
        msg = str(exc_info.value)
        assert "a" in msg or "b" in msg


# ---------------------------------------------------------------------------
# Stability (original order preserved for ties)
# ---------------------------------------------------------------------------

class TestStableOrdering:
    def test_three_independents_keep_original_order(self, tmp_path):
        """No constraints between auth, public, redis → pyproject order preserved."""
        uvl = write_uvl(tmp_path, SAMPLE_UVL)
        features = [pkg("public"), pkg("auth"), pkg("reset"), pkg("mail")]
        result = RESOLVER.resolve(features, uvl)
        # mail must come before reset; public and auth have no constraint
        assert result.index(pkg("mail")) < result.index(pkg("reset"))
        # public and auth keep their relative order (public before auth in input)
        assert result.index(pkg("public")) < result.index(pkg("auth"))
