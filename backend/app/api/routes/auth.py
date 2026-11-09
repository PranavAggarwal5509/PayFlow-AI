from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import (
    ALL_PERMISSIONS,
    ROLE_INFO,
    ROLE_PERMISSIONS,
    CurrentUser,
    Role,
    create_token,
    get_current_user,
)
from app.database.session import get_db
from app.schemas.common import ApiResponse
from app.services import user_service
from app.services.audit_service import record_audit

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)
    remember: bool = False


def _user_payload(user: CurrentUser) -> dict:
    role = Role(user.role)
    return {
        "id": user.user_id,
        "email": user.id,
        "name": user.name,
        "role": user.role,
        "role_label": ROLE_INFO[role]["label"],
        "permissions": sorted(user.permissions),
    }


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = user_service.authenticate(db, body.email, body.password)
    token, expires = create_token(user.id, user.role, settings, remember=body.remember)
    current = CurrentUser(
        id=user.email, name=user.full_name, role=user.role, user_id=str(user.id),
        permissions=frozenset(ROLE_PERMISSIONS[Role(user.role)]),
    )  # fmt: skip
    return ApiResponse(data={"token": token, "expires_at": expires, "user": _user_payload(current)})


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)):
    return ApiResponse(data=_user_payload(user))


@router.post("/logout")
def logout(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """Tokens are stateless; this records the sign-out in the audit trail."""
    record_audit(db, action="USER_LOGOUT", actor_type="USER", actor_id=user.id, description="Signed out.")
    db.commit()
    return ApiResponse(data={"ok": True})


@router.get("/roles")
def roles(settings: Settings = Depends(get_settings)):
    """Public: role catalogue + permission matrix (and demo accounts when enabled) for the sign-in page."""
    demo = (
        [
            {"email": a["email"], "name": a["full_name"], "role": a["role"].value, "password": a["password"]}
            for a in user_service.DEMO_ACCOUNTS
        ]
        if settings.enable_demo_accounts
        else []
    )
    return ApiResponse(
        data={
            "permissions": ALL_PERMISSIONS,
            "roles": [
                {"role": r.value, **ROLE_INFO[r], "permissions": sorted(ROLE_PERMISSIONS[r])} for r in Role
            ],
            "demo_accounts": demo,
        }
    )
