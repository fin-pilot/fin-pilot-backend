"""Exchange rate service.

Fetches daily rates from the National Bank of Ukraine (NBU) public API and
stores them in the ``exchange_rates`` table.  An in-memory cache avoids
repeated DB lookups during a single training/inference call.

NBU endpoint:
  GET https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange
      ?date=YYYYMMDD&json

Returns an array of objects:
  {"cc": "USD", "rate": 41.5, "txt": "Долар США", "exchangedate": "30.05.2026"}

Convention: ``rate`` means "1 target_currency = rate UAH".
To convert an amount from USD to UAH:  amount_uah = amount_usd * rate.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import date
from urllib.error import URLError

from sqlalchemy.orm import Session

from app.repositories.exchange_rate_repository import ExchangeRateRepository

logger = logging.getLogger(__name__)

_NBU_URL = (
    "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange"
    "?date={date}&json"
)
_REQUEST_TIMEOUT = 10  # seconds


class ExchangeRateService:
    """Thin wrapper around the NBU API with an in-memory rate cache."""

    def __init__(self) -> None:
        # (base_currency, target_currency, rate_date) → rate
        self._cache: dict[tuple[str, str, date], float] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def fetch_and_store(self, db: Session) -> int:
        """Fetch today's rates from NBU, persist to DB, warm the cache.

        Returns the number of currencies updated.  On network failure logs a
        warning and returns 0 so the caller can decide whether to retry.
        """
        today = date.today()
        raw = self._fetch_nbu(today)
        if raw is None:
            return 0

        rows: list[dict] = []
        for item in raw:
            cc = (item.get("cc") or "").strip().upper()
            rate = item.get("rate")
            if not cc or rate is None:
                continue
            rows.append(
                {
                    "base_currency": "UAH",
                    "target_currency": cc,
                    "rate": float(rate),
                    "rate_date": today,
                    "source": "NBU",
                }
            )
            self._cache[("UAH", cc, today)] = float(rate)

        if rows:
            ExchangeRateRepository(db).upsert_batch(rows)

        logger.info(
            "Exchange rates refreshed: %d currencies for %s", len(rows), today
        )
        return len(rows)

    def get_rate(
        self,
        db: Session,
        base: str,
        target: str,
        on_date: date,
    ) -> float:
        """Return the conversion factor: 1 *target* = X *base* units.

        Resolution order:
        1. In-memory cache (same-process, zero cost).
        2. DB lookup (backwards up to 7 days for holidays/weekends).
        3. Safe fallback of 1.0 with a warning (avoids crashing ML pipeline).
        """
        base = base.upper()
        target = target.upper()

        if base == target:
            return 1.0

        cache_key = (base, target, on_date)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        rate = ExchangeRateRepository(db).get_rate(base, target, on_date)
        if rate is not None:
            self._cache[cache_key] = rate
            return rate

        logger.warning(
            "No exchange rate found for %s→%s on %s; using 1.0 as fallback.",
            target,
            base,
            on_date,
        )
        return 1.0

    # ── Internal ──────────────────────────────────────────────────────────────

    def _fetch_nbu(self, for_date: date) -> list[dict] | None:
        url = _NBU_URL.format(date=for_date.strftime("%Y%m%d"))
        try:
            with urllib.request.urlopen(url, timeout=_REQUEST_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (URLError, OSError) as exc:
            logger.warning("NBU API unreachable: %s", exc)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("NBU API returned invalid JSON: %s", exc)
        return None


# Module-level singleton shared across the entire process lifetime.
exchange_rate_service = ExchangeRateService()
