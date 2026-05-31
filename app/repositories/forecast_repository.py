from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Forecast


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

    def save_batch(
        self,
        user_id: UUID,
        points: list[tuple[datetime, float]],
        model_type: str = "SARIMA",
    ) -> None:
        """Replace all existing forecasts for *user_id* with *points*.

        Each point is a ``(target_date, predicted_amount)`` pair.
        """
        self._db.execute(delete(Forecast).where(Forecast.user_id == user_id))
        now = datetime.now(tz=timezone.utc)
        for target_date, predicted_amount in points:
            self._db.add(
                Forecast(
                    user_id=user_id,
                    target_date=target_date,
                    predicted_amount=predicted_amount,
                    model_type=model_type,
                    created_at=now,
                )
            )
        self._db.commit()
