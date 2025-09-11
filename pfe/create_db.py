# seed.py (or wherever you run this)
from app import create_app
from app.extensions import db
from app.models.user import User, Role
from sqlalchemy import func

app = create_app()
with app.app_context():
    db.create_all()

    def get_or_create_role(name: str) -> Role:
        r = Role.query.filter_by(name=name).first()
        if not r:
            r = Role(name=name)
            db.session.add(r)
            db.session.flush()
        return r

    admin_role = get_or_create_role("admin")
    user_role  = get_or_create_role("user")

    def upsert_user(email: str, password: str, want_roles: list[Role]):
        norm_email = (email or "").strip().lower()

        # Case-insensitive lookup
        u = User.query.filter(func.lower(User.email) == norm_email).first()

        if u is None:
            # Create new
            u = User(email=norm_email)
            u.set_password(password)
            u.roles = list(set(want_roles))  # ensure unique
            db.session.add(u)
            print(f"[seed] Created user {norm_email} with roles {[r.name for r in u.roles]}")
        else:
            # Update existing: (re)apply password and ensure roles
            u.set_password(password)  # <-- reset to known value
            have = {r.name for r in u.roles}
            need = {r.name for r in want_roles}
            if need - have:
                # attach any missing roles
                roles_by_name = {r.name: r for r in Role.query.all()}
                for role_name in (need - have):
                    u.roles.append(roles_by_name[role_name])
            print(f"[seed] Updated user {norm_email} (reset password, ensured roles)")

    upsert_user("admin@pfe.local", "admin123", [admin_role, user_role])
    upsert_user("user@pfe.local",  "user123",  [user_role])

    db.session.commit()
    print("DB seeded. Admin: admin@pfe.local / admin123 | User: user@pfe.local / user123")
