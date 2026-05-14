from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.models import Forecast


class ForecastRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_by_user(self, user_id: UUID) -> list[Forecast]:
        return (
            self._db.query(Forecast)
            .filter(Forecast.user_id == user_id)
            .order_by(Forecast.target_date)
            .all()
        )
