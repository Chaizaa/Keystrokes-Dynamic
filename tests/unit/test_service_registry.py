import pytest

from app.services.registry import ServiceRegistry


def test_register_instance_and_get_returns_same_object():
    registry = ServiceRegistry()
    service = object()

    registry.register("auth", service)

    assert registry.has("auth") is True
    assert registry.get("auth") is service


def test_register_provider_is_lazy_and_memoized():
    registry = ServiceRegistry()
    calls = []

    def _provider():
        calls.append("called")
        return {"service": "biometric"}

    registry.register("biometric", provider=_provider)

    assert calls == []

    first = registry.get("biometric")
    second = registry.get("biometric")

    assert first == {"service": "biometric"}
    assert second is first
    assert calls == ["called"]


def test_register_duplicate_key_raises_without_replace():
    registry = ServiceRegistry()
    registry.register("auth", object())

    with pytest.raises(KeyError, match="already registered"):
        registry.register("auth", object())


def test_register_duplicate_key_can_replace_when_explicit():
    registry = ServiceRegistry()
    first = {"version": 1}
    second = {"version": 2}

    registry.register("auth", first)
    registry.register("auth", second, replace=True)

    assert registry.get("auth") is second


def test_get_missing_key_raises_key_error():
    registry = ServiceRegistry()

    with pytest.raises(KeyError, match="not registered"):
        registry.get("missing")


def test_register_requires_exactly_one_source():
    registry = ServiceRegistry()

    with pytest.raises(ValueError, match="exactly one"):
        registry.register("bad")

    with pytest.raises(ValueError, match="exactly one"):
        registry.register("bad", object(), provider=lambda: object())
