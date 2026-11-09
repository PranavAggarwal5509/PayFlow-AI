"""User accounts: sign-in and demo-account seeding."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import UnauthorizedError
from app.core.security import Role, hash_password, verify_password
from app.database.base import utcnow
from app.models.user import User
from app.services.audit_service import record_audit

# One fictional account per role. Passwords are public on purpose: this is a demo workspace.
DEMO_ACCOUNTS = [
    {"email": "admin@payflow.demo", "full_name": "Aarav Mehta", "role": Role.ADMIN, "password": "Admin@123"},
    {"email": "finance@payflow.demo", "full_name": "Priya Raman", "role": Role.FINANCE_MANAGER, "password": "Finance@123"},
    {"email": "reviewer@payflow.demo", "full_name": "Rohan Iyer", "role": Role.AP_REVIEWER, "password": "Review@123"},
    {"email": "clerk@payflow.demo", "full_name": "Neha Kulkarni", "role": Role.AP_CLERK, "password": "Clerk@123"},
    {"email": "auditor@payflow.demo", "full_name": "Kabir Sethi", "role": Role.AUDITOR, "password": "Audit@123"},
]


def ensure_demo_accounts(db: Session) -> int:
    """Create any missing demo account (idempotent; never overwrites an existing user)."""
    created = 0
    for account in DEMO_ACCOUNTS:
        if db.scalar(select(User).where(User.email == account["email"])):
            continue
        db.add(
            User(
                email=account["email"],
                full_name=account["full_name"],
                role=account["role"].value,
                password_hash=hash_password(account["password"]),
                is_demo=True,
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    # Same message either way, so the endpoint does not reveal which emails exist.
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Incorrect email or password.")
    user.last_login_at = utcnow()
    record_audit(db, action="USER_LOGIN", actor_type="USER", actor_id=user.email, description=f"Signed in as {user.role}.")
    db.commit()
    return user
