import config as config_module

from app import create_app, csrf, limiter, login_manager
from app.blueprints.api import service_registry as api_service_registry


def _build_test_config(**overrides):
    config = {
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-secret-key",
        "RATELIMIT_ENABLED": False,
    }
    config.update(overrides)
    return config


def test_bootstrap_registers_expected_blueprints(app):
    expected = {"main", "auth", "api", "admin", "dataset", "health"}

    assert expected.issubset(set(app.blueprints.keys()))


def test_bootstrap_initializes_expected_extensions(app):
    expected = {"sqlalchemy", "migrate", "cache", "socketio", "csrf", "mail"}

    assert expected.issubset(set(app.extensions.keys()))


def test_bootstrap_attaches_service_registry_extension(app):
    assert app.extensions.get("service_registry") is api_service_registry


def test_api_blueprint_is_exempt_from_csrf(app):
    api_blueprint = app.blueprints["api"]

    assert api_blueprint in csrf._exempt_blueprints


def test_login_manager_defaults_are_configured(app):
    assert login_manager.login_view == "auth.login_page"
    assert login_manager.login_message_category == "info"


def test_invalid_ml_backend_is_normalized_to_rf():
    local_app = create_app(_build_test_config(ML_BACKEND="invalid-value"))

    assert local_app.config["ML_BACKEND"] == "rf"


def test_rate_limiter_respects_config_toggle():
    create_app(_build_test_config(RATELIMIT_ENABLED=False))
    assert limiter.enabled is False

    create_app(_build_test_config(RATELIMIT_ENABLED=True, DEV_LENIENT_RATELIMIT=False))
    assert limiter.enabled is True


def test_create_app_named_config_calls_validate_config(monkeypatch):
    calls = []

    def _spy_validate(config_class):
        calls.append(config_class)

    monkeypatch.setattr(config_module, "validate_config", _spy_validate)

    local_app = create_app("testing")

    assert local_app.config["TESTING"] is True
    assert calls
    assert calls[-1] is config_module.TestingConfig
