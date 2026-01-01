from app import create_app
from app.services.auth_service import AuthService

app = create_app("development")
with app.app_context():
    auth = AuthService()
    res = auth.create_user("migrationtest", "pass123", email="test@example.com")
    print("create_user result:", res)
