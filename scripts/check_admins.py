import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app

app = create_app('development')

with app.app_context():
    from app.models import db, User

    admins = db.session.query(User).filter_by(role='admin').all()
    if not admins:
        print('NO_ADMINS_FOUND')
    else:
        for u in admins:
            print(f"{u.id}\t{u.username}\t{u.email}\tcreated:{u.created_at}\tlast_login:{getattr(u, 'last_login', None)}")
