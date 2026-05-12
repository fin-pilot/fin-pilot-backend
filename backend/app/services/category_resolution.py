"""Map ML category labels to persisted Category rows."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Category, TransactionType


def resolve_category_for_label(
    db: Session,
    user_id: UUID,
    label: str,
    category_type: TransactionType = TransactionType.EXPENSE,
) -> Optional[Category]:
    name_norm = (label or "").strip().lower()
    if not name_norm:
        return None

    row = (
        db.query(Category)
        .filter(
            Category.user_id == user_id,
            Category.type == category_type,
            func.lower(Category.name) == name_norm,
        )
        .first()
    )
    if row:
        return row

    return (
        db.query(Category)
        .filter(
            Category.user_id.is_(None),
            Category.type == category_type,
            func.lower(Category.name) == name_norm,
        )
        .first()
    )
