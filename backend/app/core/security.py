"""Authentication boundaries.

* Public API: a documented *demo user* (modular — swap `get_current_user` for real JWT/OIDC later).
"""

from dataclasses import dataclass

from fastapi import Depends

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class CurrentUser:
    id: str
    name: str
    role: str  # ADMIN | REVIEWER


def get_current_user(settings: Settings = Depends(get_settings)) -> CurrentUser:
    return CurrentUser(id=settings.demo_user_email, name=settings.demo_user_name, role="ADMIN")
