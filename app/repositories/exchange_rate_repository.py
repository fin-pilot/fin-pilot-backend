from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ExchangeRate


class ExchangeRateRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_rate(self, base: str, target: str, on_date: date) -> float | None:
        """Return rate for the closest available date on or before *on_date*.

        Searches up to 7 days backwards to handle weekends and public holidays
        when the NBU does not publish new rates.
        """
        for delta in range(8):
            check_date = on_date - timedelta(days=delta)
            row = self._db.execute(
                select(ExchangeRate).where(
                    ExchangeRate.base_currency == base,
                    ExchangeRate.target_currency == target,
                    ExchangeRate.rate_date == check_date,
                )
            ).scalar_one_or_none()
            if row is not None:
                return float(row.rate)
        return None

    def upsert_batch(self, rows: list[dict]) -> None:
        """Insert or update a list of rate dicts.

        Each dict must contain: base_currency, target_currency, rate,
        rate_date, source.
        """
        for data in rows:
            existing = self._db.execute(
                select(ExchangeRate).where(
                    ExchangeRate.base_currency == data["base_currency"],
                    ExchangeRate.target_currency == data["target_currency"],
                    ExchangeRate.rate_date == data["rate_date"],
                )
            ).scalar_one_or_none()

            if existing is not None:
                existing.rate = data["rate"]
                existing.source = data.get("source", "NBU")
            else:
                self._db.add(
                    ExchangeRate(
                        base_currency=data["base_currency"],
                        target_currency=data["target_currency"],
                        rate=data["rate"],
                        rate_date=data["rate_date"],
                        source=data.get("source", "NBU"),
                    )
                )
        self._db.commit()

    def latest_date(self) -> date | None:
        """Return the most recent rate_date stored in the table."""
        from sqlalchemy import func

        result = self._db.execute(
            select(func.max(ExchangeRate.rate_date))
        ).scalar_one_or_none()
        return result
