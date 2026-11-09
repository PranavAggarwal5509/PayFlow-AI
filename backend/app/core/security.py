"""Authentication and role-based access control.

* Passwords: PBKDF2-HMAC-SHA256 with a per-user salt (stdlib, no extra dependency).
* Sessions: compact HMAC-SHA256 signed bearer tokens (`payload.signature`, base64url), carrying
  the user id, role and expiry. Every request re-loads the user, so deactivating an account or
  changing a role takes effect immediately.
* Authorisation: a role → permission map. Routes declare the permission they need with
  `Depends(require("invoices:upload"))`; the frontend reads the same map from /auth/me.
"""

from __future__ import annotations

import base64
import enum
import hashlib
import hmac
import json
import secrets
import time
import uuid
from dataclasses import dataclass, field

from fastapi import Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.database.session import get_db


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    FINANCE_MANAGER = "FINANCE_MANAGER"
    AP_REVIEWER = "AP_REVIEWER"
    AP_CLERK = "AP_CLERK"
    AUDITOR = "AUDITOR"


class Permission:
    INVOICES_VIEW = "invoices:view"
    INVOICES_UPLOAD = "invoices:upload"
    REVIEW_ACT = "review:act"
    REVIEW_HIGH_VALUE = "review:approve_high_value"
    MASTERDATA_VIEW = "masterdata:view"
    MASTERDATA_EDIT = "masterdata:edit"
    SETTINGS_VIEW = "settings:view"
    DEVELOPER_VIEW = "developer:view"
    USERS_MANAGE = "users:manage"
    DEMO_RESET = "demo:reset"


ALL_PERMISSIONS = [v for k, v in vars(Permission).items() if not k.startswith("_")]

ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.ADMIN: set(ALL_PERMISSIONS),
    Role.FINANCE_MANAGER: {
        Permission.INVOICES_VIEW, Permission.INVOICES_UPLOAD, Permission.REVIEW_ACT,
        Permission.REVIEW_HIGH_VALUE, Permission.MASTERDATA_VIEW, Permission.SETTINGS_VIEW,
    },
    Role.AP_REVIEWER: {
        Permission.INVOICES_VIEW, Permission.INVOICES_UPLOAD, Permission.REVIEW_ACT,
        Permission.MASTERDATA_VIEW, Permission.SETTINGS_VIEW,
    },
    Role.AP_CLERK: {Permission.INVOICES_VIEW, Permission.INVOICES_UPLOAD, Permission.MASTERDATA_VIEW},
    Role.AUDITOR: {Permission.INVOICES_VIEW, Permission.MASTERDATA_VIEW, Permission.SETTINGS_VIEW},
}  # fmt: skip

ROLE_INFO: dict[Role, dict[str, str]] = {
    Role.ADMIN: {
        "label": "Administrator",
        "summary": "Full access: every page, every action, master data and system configuration.",
    },
    Role.FINANCE_MANAGER: {
        "label": "Finance Manager",
        "summary": "Approves exceptions including invoices above the auto-approval limit.",
    },
    Role.AP_REVIEWER: {
        "label": "AP Reviewer",
        "summary": "Works the review queue: approve, reject or ask for clarification (up to the limit).",
    },
    Role.AP_CLERK: {
        "label": "AP Clerk",
        "summary": "Uploads and tracks invoices. Cannot make review decisions.",
    },
    Role.AUDITOR: {
        "label": "Auditor",
        "summary": "Read-only access to invoices, decisions, evidence and controls.",
    },
}


def permissions_for(role: str) -> set[str]:
    try:
        return ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return set()


# ------------------------------------------------------------------ passwords
_ITERATIONS = 210_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt, digest = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(iterations))
        return hmac.compare_digest(candidate, _unb64(digest))
    except (ValueError, TypeError):
        return False


# ------------------------------------------------------------------ tokens
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_token(user_id: uuid.UUID, role: str, settings: Settings, *, remember: bool = False) -> tuple[str, int]:
    ttl = settings.auth_remember_ttl_hours if remember else settings.auth_session_ttl_hours
    expires = int(time.time()) + ttl * 3600
    payload = _b64(json.dumps({"sub": str(user_id), "role": role, "exp": expires}, separators=(",", ":")).encode())
    signature = _b64(hmac.new(settings.auth_secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}", expires


def decode_token(token: str, settings: Settings) -> dict:
    try:
        payload, signature = token.split(".")
    except ValueError as exc:
        raise UnauthorizedError("Malformed session token.") from exc
    expected = _b64(hmac.new(settings.auth_secret.encode(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise UnauthorizedError("Invalid session token.")
    data = json.loads(_unb64(payload))
    if data.get("exp", 0) < time.time():
        raise UnauthorizedError("Your session has expired. Please sign in again.")
    return data


# ------------------------------------------------------------------ request dependencies
@dataclass(frozen=True)
class CurrentUser:
    id: str  # email — what audit logs and `uploaded_by` record
    name: str
    role: str
    user_id: str | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def get_current_user(
    request: Request,
    access_token: str | None = Query(default=None, include_in_schema=False),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Bearer token from the Authorization header, or `?access_token=` for EventSource / PDF links."""
    from app.models.user import User

    header = request.headers.get("Authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else access_token
    if not token:
        raise UnauthorizedError("Sign in to continue.")
    data = decode_token(token, settings)
    try:
        user = db.get(User, uuid.UUID(data["sub"]))
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Invalid session token.") from exc
    if user is None or not user.is_active:
        raise UnauthorizedError("This account is no longer active.")
    return CurrentUser(
        id=user.email,
        name=user.full_name,
        role=user.role,
        user_id=str(user.id),
        permissions=frozenset(permissions_for(user.role)),
    )


def require(permission: str):
    """Route dependency: the signed-in user must hold `permission`."""

    def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.can(permission):
            label = ROLE_INFO.get(Role(user.role), {}).get("label", user.role) if user.role in Role.__members__ else user.role
            raise ForbiddenError(f"Your role ({label}) does not have permission for this action.")
        return user

    return checker
