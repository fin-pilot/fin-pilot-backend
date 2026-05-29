from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import Forecast


class ForecastRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_by_user(self, user_id: UUID) -> list[Forecast]:
        stmt = (
            select(Forecast)
            .where(Forecast.user_id == user_id)
            .order_by(Forecast.target_date)
        )

        return list(self._db.scalars(stmt).all())
