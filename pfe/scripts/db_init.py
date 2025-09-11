# init_pfe_db.py
# Creates MySQL DB 'pfe_db' with users/roles models + relation, then seeds data.

import pymysql
from sqlalchemy import (
    create_engine, Table, Column, Integer, String, DateTime, ForeignKey, MetaData, select, func, text
)
from sqlalchemy.orm import declarative_base, relationship, Session
from werkzeug.security import generate_password_hash
import datetime

# ---------- CONFIGURE THESE IF NEEDED ----------
MYSQL_HOST = "127.0.0.1"     # XAMPP MySQL host
MYSQL_PORT = 3306            # Use 3306 or 3307 (check C:\xampp\mysql\bin\my.ini)
MYSQL_USER = "root"          # XAMPP default user
MYSQL_PASS = ""              # XAMPP default has empty password
DB_NAME    = "pfe_db"        # Target DB name to create/use
# ----------------------------------------------

# 1) Ensure database exists (server-level connection, no database selected)
print(f"Ensuring database '{DB_NAME}' exists on {MYSQL_HOST}:{MYSQL_PORT}...")
server_conn = pymysql.connect(
    host=MYSQL_HOST, port=MYSQL_PORT,
    user=MYSQL_USER, password=MYSQL_PASS,
    charset="utf8mb4", autocommit=True
)
with server_conn.cursor() as cur:
    cur.execute(
        f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    )
server_conn.close()
print("✓ Database ensured.")

# 2) SQLAlchemy engine bound to the target DB
dsn = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASS}@{MYSQL_HOST}:{MYSQL_PORT}/{DB_NAME}?charset=utf8mb4"
engine = create_engine(dsn, echo=False, future=True)

Base = declarative_base()

# 3) Association table: many-to-many User<->Role
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

class Role(Base):
    __tablename__ = "roles"
    id   = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(32), unique=True, nullable=False)

    def __repr__(self):
        return f"<Role {self.name}>"

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    email         = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at    = Column(DateTime, default=datetime.datetime.utcnow)

    roles = relationship("Role", secondary=user_roles, backref="users", lazy="joined")

    def __repr__(self):
        return f"<User {self.email}>"

# 4) Create all tables
print("Creating tables (if missing)...")
Base.metadata.create_all(engine)
print("✓ Tables ready.")

# 5) Seed roles and users idempotently
with Session(engine) as session:
    # Ensure roles
    def get_or_create_role(name: str) -> Role:
        r = session.execute(select(Role).where(Role.name == name)).scalar_one_or_none()
        if not r:
            r = Role(name=name)
            session.add(r)
            session.flush()  # get id
        return r

    admin_role = get_or_create_role("admin")
    user_role  = get_or_create_role("user")

    # Ensure admin user
    admin = session.execute(select(User).where(User.email == "admin@pfe.local")).scalar_one_or_none()
    if not admin:
        admin = User(
            email="admin@pfe.local",
            password_hash=generate_password_hash("admin123"),
            created_at=datetime.datetime.utcnow(),
        )
        admin.roles = [admin_role, user_role]
        session.add(admin)

    # Ensure normal user
    user = session.execute(select(User).where(User.email == "user@pfe.local")).scalar_one_or_none()
    if not user:
        user = User(
            email="user@pfe.local",
            password_hash=generate_password_hash("user123"),
            created_at=datetime.datetime.utcnow(),
        )
        user.roles = [user_role]
        session.add(user)

    session.commit()

print("✓ Seed complete.")
print(f"✅ Done. Open phpMyAdmin and select the '{DB_NAME}' database to see the tables.")

# Optional: quick sanity query
with engine.connect() as conn:
    total_users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
    total_roles = conn.execute(text("SELECT COUNT(*) FROM roles")).scalar()
    print(f"Users: {total_users}, Roles: {total_roles}")
