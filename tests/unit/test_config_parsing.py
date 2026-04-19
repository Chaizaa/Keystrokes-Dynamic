import importlib

import pytest


def _reload_config_module():
    import config as config_module

    return importlib.reload(config_module)


def test_invalid_ml_backend_defaults_to_rf(monkeypatch):
    monkeypatch.setenv("ML_BACKEND", "invalid-value")

    config_module = _reload_config_module()

    assert config_module.Config.ML_BACKEND == "rf"


def test_validate_config_rejects_threshold_out_of_range(monkeypatch):
    monkeypatch.setenv("VERIFICATION_THRESHOLD", "1.5")

    config_module = _reload_config_module()

    with pytest.raises(ValueError, match="VERIFICATION_THRESHOLD"):
        config_module.validate_config(config_module.Config)


def test_validate_config_rejects_recommended_less_than_min(monkeypatch):
    monkeypatch.setenv("MIN_ENROLLMENT_SAMPLES", "10")
    monkeypatch.setenv("RECOMMENDED_SAMPLES", "5")

    config_module = _reload_config_module()

    with pytest.raises(ValueError, match="RECOMMENDED_SAMPLES"):
        config_module.validate_config(config_module.Config)


def test_validate_production_requires_secret_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "")

    config_module = _reload_config_module()

    with pytest.raises(ValueError, match="SECRET_KEY"):
        config_module.validate_config(config_module.ProductionConfig)


def test_validate_config_rejects_invalid_samesite(monkeypatch):
    monkeypatch.setenv("SESSION_COOKIE_SAMESITE", "Invalid")

    config_module = _reload_config_module()

    with pytest.raises(ValueError, match="SESSION_COOKIE_SAMESITE"):
        config_module.validate_config(config_module.Config)


def test_testing_config_uses_in_memory_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_TYPE", raising=False)

    config_module = _reload_config_module()

    assert config_module.TestingConfig.SQLALCHEMY_DATABASE_URI == "sqlite:///:memory:"
