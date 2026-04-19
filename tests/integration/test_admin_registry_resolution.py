from app.services import ServiceRegistry


def test_admin_login_uses_app_extensions_registry(client, app, db_session, monkeypatch):
    from app.models import User, db

    calls = []

    class _FakeAuthService:
        def login_user_session(self, user):
            calls.append(user.username)
            return True

    replacement_registry = ServiceRegistry()
    replacement_registry.register("auth_service", _FakeAuthService())

    admin = User(username="admin_registry_user")
    admin.set_password("AdminPass123!")
    admin.role = "admin"
    db.session.add(admin)
    db.session.commit()

    with app.app_context():
        monkeypatch.setitem(app.extensions, "service_registry", replacement_registry)
        resp = client.post(
            "/admin/login",
            json={"username": "admin_registry_user", "password": "AdminPass123!"},
        )

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert calls == ["admin_registry_user"]


def test_admin_login_requires_registry_auth_service(client, app, db_session, monkeypatch):
    from app.models import User, db

    admin = User(username="admin_registry_missing")
    admin.set_password("AdminPass123!")
    admin.role = "admin"
    db.session.add(admin)
    db.session.commit()

    with app.app_context():
        monkeypatch.delitem(app.extensions, "service_registry", raising=False)
        resp = client.post(
            "/admin/login",
            json={"username": "admin_registry_missing", "password": "AdminPass123!"},
        )

    assert resp.status_code == 500
    data = resp.get_json()
    assert data["success"] is False
