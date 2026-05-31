"""FastAPI dependency that resolves the active locale for a request.

Resolution order
----------------
1. ``Accept-Language`` HTTP header  (``uk`` or ``en``; first matching tag wins).
2. ``current_user.locale`` stored in the DB (set via PATCH /api/users/me).
3. Hard fallback: ``"uk"``.

Usage in a route
----------------
from app.i18n.dependencies import get_locale

@router.get("/recommendations")
def get_recommendations(
    locale: str = Depends(get_locale),
    ...
):
    ...
"""

from __future__ import annotations

from fastapi import Depends, Header

from app.api.dependencies import get_current_user
from app.db.models import User

_SUPPORTED = {"uk", "en"}


def get_locale(
    accept_language: str | None = Header(None, alias="Accept-Language"),
    current_user: User = Depends(get_current_user),
) -> str:
    """Return the two-letter locale code to use for this request."""
    if accept_language:
        for tag in accept_language.replace(" ", "").split(","):
            lang = tag.split(";")[0].split("-")[0].lower()
            if lang in _SUPPORTED:
                return lang

    if current_user.locale in _SUPPORTED:
        return current_user.locale

    return "uk"
