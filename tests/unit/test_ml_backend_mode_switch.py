import app.services.biometric_service as biometric_module


class _FakeTrainResult:
    def __init__(
        self,
        *,
        success=True,
        reason="trained",
        message="ok",
        model_id=1,
        threshold=0.5,
        eer=0.1,
        metrics=None,
    ):
        self.success = success
        self.reason = reason
        self.message = message
        self.model_id = model_id
        self.threshold = threshold
        self.eer = eer
        self.metrics = metrics or {"accuracy": 1.0}


class _FakeBackendService:
    def __init__(self, *, verify_payload=None, model_exists=True):
        self.verify_payload = verify_payload or {
            "success": True,
            "verified": True,
            "score": 0.93,
            "threshold": 0.5,
            "confidence": "high",
            "model_id": 10,
            "method": "fake",
        }
        self.model_exists = model_exists
        self.train_calls = []
        self.verify_calls = []
        self.get_model_calls = []

    def train_user_model(self, username, force=False):
        self.train_calls.append((username, force))
        return _FakeTrainResult(model_id=99)

    def get_model_row(self, username):
        self.get_model_calls.append(username)
        return object() if self.model_exists else None

    def verify(self, username, features):
        self.verify_calls.append((username, dict(features or {})))
        return dict(self.verify_payload)


class _ScheduleSpy:
    def __init__(self):
        self.calls = []

    def __call__(self, app, username, force=False):
        self.calls.append((username, force))
        return True


def test_active_backend_uses_rf_for_invalid_config(app):
    app.config["ML_BACKEND"] = "invalid-value"
    svc = biometric_module.BiometricService()

    assert svc._active_backend_name() == "rf"


def test_active_backend_uses_svm_from_app_config(app):
    app.config["ML_BACKEND"] = "svm"
    svc = biometric_module.BiometricService()

    assert svc._active_backend_name() == "svm"


def test_train_user_model_dispatches_to_svm_backend(app, monkeypatch):
    app.config["ML_BACKEND"] = "svm"
    rf_service = _FakeBackendService()
    svm_service = _FakeBackendService()

    monkeypatch.setattr(biometric_module, "ml_model_service", rf_service)
    monkeypatch.setattr(biometric_module, "svm_model_service", svm_service)

    svc = biometric_module.BiometricService()
    result = svc.train_user_model("alice", force=True)

    assert result["success"] is True
    assert result["backend"] == "svm"
    assert svm_service.train_calls == [("alice", True)]
    assert rf_service.train_calls == []


def test_verify_dispatches_to_rf_backend_and_preserves_method(app, monkeypatch):
    app.config["ML_BACKEND"] = "rf"

    rf_service = _FakeBackendService(
        verify_payload={
            "success": True,
            "verified": True,
            "score": 0.81,
            "threshold": 0.66,
            "confidence": "medium",
            "model_id": 7,
            "method": "random_forest",
        },
        model_exists=True,
    )
    svm_service = _FakeBackendService(model_exists=True)

    monkeypatch.setattr(biometric_module, "ml_model_service", rf_service)
    monkeypatch.setattr(biometric_module, "svm_model_service", svm_service)

    svc = biometric_module.BiometricService()
    result = svc.verify_keystroke_sample("alice", {"H_mean": 0.1})

    assert result["success"] is True
    assert result["verified"] is True
    assert result["method"] == "random_forest"
    assert len(rf_service.verify_calls) == 1
    assert len(svm_service.verify_calls) == 0


def test_verify_missing_model_schedules_svm_training(app, monkeypatch):
    app.config["ML_BACKEND"] = "svm"

    rf_service = _FakeBackendService(model_exists=True)
    svm_service = _FakeBackendService(model_exists=False)
    rf_schedule = _ScheduleSpy()
    svm_schedule = _ScheduleSpy()

    monkeypatch.setattr(biometric_module, "ml_model_service", rf_service)
    monkeypatch.setattr(biometric_module, "svm_model_service", svm_service)
    monkeypatch.setattr(biometric_module, "schedule_rf_background_training", rf_schedule)
    monkeypatch.setattr(biometric_module, "schedule_svm_background_training", svm_schedule)
    monkeypatch.setattr(biometric_module, "rf_is_training_in_progress", lambda _u: False)
    monkeypatch.setattr(biometric_module, "svm_is_training_in_progress", lambda _u: False)

    svc = biometric_module.BiometricService()
    result = svc.verify_keystroke_sample("alice", {"H_mean": 0.1})

    assert result["success"] is False
    assert result["reason"] == "training_started"
    assert svm_schedule.calls == [("alice", False)]
    assert rf_schedule.calls == []
    assert len(svm_service.verify_calls) == 0
