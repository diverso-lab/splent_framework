"""Tests for the refinement system: registry, parser, and validator."""

import pytest

from splent_framework.refinement.registry import (
    RefinementEntry,
    RefinementRegistry,
)
from splent_framework.refinement.parser import (
    parse_extensible,
    parse_refinement,
    ExtensibleContract,
    RefinementConfig,
)
from splent_framework.refinement.validator import validate_refinements


# ── Registry ──────────────────────────────────────────────────────────────────


class TestRefinementRegistry:
    def test_empty_registry(self):
        reg = RefinementRegistry()
        assert reg.all_entries() == []
        assert reg.get_overrides("auth", "service") == []
        assert reg.get_bases() == set()
        assert reg.get_refiners() == set()

    def test_register_and_retrieve(self):
        reg = RefinementRegistry()
        entry = RefinementEntry(
            refiner="auth_2fa",
            base="auth",
            category="service",
            target="AuthenticationService",
            replacement="AuthenticationService2FA",
        )
        reg.register(entry)

        assert len(reg.all_entries()) == 1
        assert reg.get_overrides("auth", "service") == [entry]
        assert reg.get_overrides("auth", "template") == []
        assert reg.get_overrides("other", "service") == []
        assert reg.is_refiner("auth_2fa")
        assert not reg.is_refiner("auth")
        assert "auth" in reg.get_bases()

    def test_multiple_entries(self):
        reg = RefinementRegistry()
        e1 = RefinementEntry(
            refiner="auth_2fa", base="auth", category="service",
            target="AuthService", replacement="AuthService2FA",
        )
        e2 = RefinementEntry(
            refiner="auth_2fa", base="auth", category="template",
            target="auth/login.html",
        )
        reg.register(e1)
        reg.register(e2)

        assert len(reg.all_entries()) == 2
        assert reg.get_overrides("auth", "service") == [e1]
        assert reg.get_overrides("auth", "template") == [e2]
        assert reg.get_all_for_base("auth") == {
            "service": [e1],
            "template": [e2],
        }

    def test_clear(self):
        reg = RefinementRegistry()
        reg.register(RefinementEntry(
            refiner="x", base="y", category="service", target="S",
        ))
        assert len(reg.all_entries()) == 1
        reg.clear()
        assert len(reg.all_entries()) == 0
        assert reg.get_bases() == set()


# ── Parser ────────────────────────────────────────────────────────────────────


class TestParseExtensible:
    def test_empty_dict(self):
        ext = parse_extensible({})
        assert ext.services == []
        assert ext.templates == []
        assert ext.models == []
        assert ext.hooks == []
        assert ext.routes is False

    def test_full_declaration(self):
        ext = parse_extensible({
            "services": ["AuthenticationService"],
            "templates": ["auth/login_form.html", "auth/signup_form.html"],
            "models": ["User"],
            "hooks": ["layout.anonymous_sidebar"],
            "routes": True,
        })
        assert ext.services == ["AuthenticationService"]
        assert ext.templates == ["auth/login_form.html", "auth/signup_form.html"]
        assert ext.models == ["User"]
        assert ext.hooks == ["layout.anonymous_sidebar"]
        assert ext.routes is True

    def test_missing_keys_default(self):
        ext = parse_extensible({"services": ["Svc"]})
        assert ext.services == ["Svc"]
        assert ext.templates == []
        assert ext.routes is False


class TestParseRefinement:
    def test_no_refines_returns_none(self):
        assert parse_refinement({}) is None
        assert parse_refinement({"overrides": {}}) is None

    def test_minimal_refinement(self):
        config = parse_refinement({"refines": "splent_feature_auth"})
        assert config is not None
        assert config.refines == "splent_feature_auth"
        assert config.overrides_services == []
        assert config.extends_models == []

    def test_full_refinement(self):
        raw = {
            "refines": "splent_feature_auth",
            "overrides": {
                "services": [{"target": "AuthService", "replacement": "AuthService2FA"}],
                "templates": [{"target": "auth/login.html"}],
                "hooks": [{"target": "layout.sidebar"}],
            },
            "extends": {
                "models": [{"target": "User", "mixin": "User2FAMixin"}],
                "routes": [{"blueprint": "auth", "module": "routes_2fa"}],
            },
        }
        config = parse_refinement(raw)
        assert config.refines == "splent_feature_auth"
        assert len(config.overrides_services) == 1
        assert config.overrides_services[0].target == "AuthService"
        assert config.overrides_services[0].replacement == "AuthService2FA"
        assert len(config.overrides_templates) == 1
        assert config.overrides_templates[0].target == "auth/login.html"
        assert len(config.extends_models) == 1
        assert config.extends_models[0].mixin == "User2FAMixin"
        assert len(config.adds_routes) == 1
        assert config.adds_routes[0].blueprint == "auth"


# ── Validator ─────────────────────────────────────────────────────────────────


class TestValidator:
    def _ext(self, **kwargs) -> ExtensibleContract:
        return ExtensibleContract(**kwargs)

    def _ref(self, refines, **kwargs) -> RefinementConfig:
        return RefinementConfig(refines=refines, **kwargs)

    def test_valid_service_override(self):
        from splent_framework.refinement.parser import RefinementOverride

        errors = validate_refinements(
            refinements={"auth_2fa": self._ref(
                "auth",
                overrides_services=[RefinementOverride("AuthService", "AuthService2FA")],
            )},
            extensibles={"auth": self._ext(services=["AuthService"])},
            known_features={"auth", "auth_2fa"},
        )
        assert errors == []

    def test_invalid_service_not_extensible(self):
        from splent_framework.refinement.parser import RefinementOverride

        errors = validate_refinements(
            refinements={"auth_2fa": self._ref(
                "auth",
                overrides_services=[RefinementOverride("AuthService", "X")],
            )},
            extensibles={"auth": self._ext()},  # empty extensible
            known_features={"auth", "auth_2fa"},
        )
        assert len(errors) == 1
        assert "does not declare it as extensible" in errors[0]

    def test_base_feature_not_in_product(self):
        errors = validate_refinements(
            refinements={"auth_2fa": self._ref("auth")},
            extensibles={},
            known_features={"auth_2fa"},  # auth not here
        )
        assert len(errors) == 1
        assert "not declared in the product" in errors[0]

    def test_duplicate_override_detected(self):
        from splent_framework.refinement.parser import RefinementOverride

        errors = validate_refinements(
            refinements={
                "auth_2fa": self._ref(
                    "auth",
                    overrides_services=[RefinementOverride("AuthService", "X")],
                ),
                "auth_sso": self._ref(
                    "auth",
                    overrides_services=[RefinementOverride("AuthService", "Y")],
                ),
            },
            extensibles={"auth": self._ext(services=["AuthService"])},
            known_features={"auth", "auth_2fa", "auth_sso"},
        )
        assert len(errors) == 1
        assert "already overridden" in errors[0]

    def test_valid_template_override(self):
        from splent_framework.refinement.parser import RefinementOverride

        errors = validate_refinements(
            refinements={"auth_2fa": self._ref(
                "auth",
                overrides_templates=[RefinementOverride("auth/login.html")],
            )},
            extensibles={"auth": self._ext(templates=["auth/login.html"])},
            known_features={"auth", "auth_2fa"},
        )
        assert errors == []

    def test_valid_model_extension(self):
        from splent_framework.refinement.parser import RefinementModelExtension

        errors = validate_refinements(
            refinements={"auth_2fa": self._ref(
                "auth",
                extends_models=[RefinementModelExtension("User", "User2FAMixin")],
            )},
            extensibles={"auth": self._ext(models=["User"])},
            known_features={"auth", "auth_2fa"},
        )
        assert errors == []

    def test_route_addition_not_allowed(self):
        from splent_framework.refinement.parser import RefinementRouteAddition

        errors = validate_refinements(
            refinements={"auth_2fa": self._ref(
                "auth",
                adds_routes=[RefinementRouteAddition("auth", "routes_2fa")],
            )},
            extensibles={"auth": self._ext(routes=False)},
            known_features={"auth", "auth_2fa"},
        )
        assert len(errors) == 1
        assert "does not declare routes as extensible" in errors[0]

    def test_route_addition_allowed(self):
        from splent_framework.refinement.parser import RefinementRouteAddition

        errors = validate_refinements(
            refinements={"auth_2fa": self._ref(
                "auth",
                adds_routes=[RefinementRouteAddition("auth", "routes_2fa")],
            )},
            extensibles={"auth": self._ext(routes=True)},
            known_features={"auth", "auth_2fa"},
        )
        assert errors == []

    def test_no_refinements_passes(self):
        errors = validate_refinements(
            refinements={},
            extensibles={"auth": self._ext(services=["X"])},
            known_features={"auth"},
        )
        assert errors == []

    def test_feature_without_extensible_blocks_all(self):
        from splent_framework.refinement.parser import RefinementOverride

        errors = validate_refinements(
            refinements={"x": self._ref(
                "auth",
                overrides_services=[RefinementOverride("Svc", "Svc2")],
            )},
            extensibles={},  # auth has no extensible declaration
            known_features={"auth", "x"},
        )
        assert len(errors) == 1
        assert "does not declare it as extensible" in errors[0]
