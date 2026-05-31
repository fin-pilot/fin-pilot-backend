"""BackendMLService — thin orchestration layer between FastAPI and fin_pilot_ml.

Responsibilities
----------------
- Owns one shared ``fin_pilot_ml.MLService`` instance for the global categoriser
  (TF-IDF + LinearSVC, user-agnostic).
- Constructs per-user ``fin_pilot_ml.MLService`` instances for SARIMA inference,
  using ``artifacts/forecasting/models/sarima_{user_id}.pkl`` paths.
- Maps SQLAlchemy ORM objects to ``fin_pilot_ml`` Pydantic schemas.
- Offloads all heavy SARIMA computation to a thread pool via
  ``asyncio.to_thread`` so the Uvicorn event loop is never blocked.
- Maintains ``UserMLState`` rows to expose training progress to the API.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from fin_pilot_ml import MLService as _MLFacade
from fin_pilot_ml.schemas import (
    CategoriseRequest,
    ForecastRequest,
    ForecastResponse,
    RecommendationRequest,
    RecommendationResponse,
    TransactionRecord,
)

from app.db.models import (
    Account,
    Budget,
    Category,
    MLTrainingStatus,
    Transaction,
    TransactionType,
    UserMLState,
    UserTransactionRule,
)
from app.repositories.forecast_repository import ForecastRepository
from app.utils.model_loader import CATEGORIZER_MODEL_PATH, FORECASTER_MODEL_PATH

logger = logging.getLogger(__name__)

# ── Artifact paths ────────────────────────────────────────────────────────────

_SARIMA_DIR = Path("artifacts/forecasting/models")
_CATEGORISER_PATH = Path(CATEGORIZER_MODEL_PATH)


def _user_sarima_path(user_id: UUID) -> Path:
    return _SARIMA_DIR / f"sarima_{user_id}.pkl"


# ── Global (shared) ML facade for categorisation ─────────────────────────────

_global_facade = _MLFacade(
    sarima_model_path=Path(FORECASTER_MODEL_PATH),
    categoriser_model_path=_CATEGORISER_PATH,
)


# ── Per-user facade factory (SARIMA only) ─────────────────────────────────────

def _load_user_facade(user_id: UUID) -> _MLFacade:
    """Construct and load a user-specific MLFacade for SARIMA inference."""
    svc = _MLFacade(
        sarima_model_path=_user_sarima_path(user_id),
        categoriser_model_path=_CATEGORISER_PATH,
    )
    svc.load()
    return svc


# ── DB helpers ────────────────────────────────────────────────────────────────

def _query_expense_transactions(db: Session, user_id: UUID) -> list[Transaction]:
    """Return all EXPENSE transactions for *user_id*, ordered by date asc."""
    stmt = (
        select(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .where(
            Account.user_id == user_id,
            Transaction.transaction_type == TransactionType.EXPENSE,
        )
        .order_by(Transaction.transaction_date.asc())
    )
    return list(db.execute(stmt).scalars().all())


def _query_all_transactions(db: Session, user_id: UUID) -> list[Transaction]:
    """Return all transactions (income + expense) for *user_id* in the last 90 days."""
    from datetime import timedelta
    from datetime import date as date_type

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=90)
    stmt = (
        select(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .where(
            Account.user_id == user_id,
            Transaction.transaction_date >= cutoff,
        )
        .order_by(Transaction.transaction_date.asc())
    )
    return list(db.execute(stmt).scalars().all())


def _to_transaction_records(txs: list[Transaction]) -> list[TransactionRecord]:
    records: list[TransactionRecord] = []
    for tx in txs:
        tx_type = (
            "debit" if tx.transaction_type == TransactionType.EXPENSE else "credit"
        )
        category_name: str | None = tx.category.name if tx.category else None
        records.append(
            TransactionRecord(
                date=tx.transaction_date.date().isoformat(),
                amount=float(tx.amount),
                transaction_type=tx_type,
                description=tx.description or "",
                category=category_name,
            )
        )
    return records


def _get_or_create_ml_state(db: Session, user_id: UUID) -> UserMLState:
    state = db.execute(
        select(UserMLState).where(UserMLState.user_id == user_id)
    ).scalar_one_or_none()
    if state is None:
        state = UserMLState(user_id=user_id)
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


# ── Main service class ────────────────────────────────────────────────────────

class BackendMLService:
    """Orchestration layer exposed to API routes."""

    # ── Startup ───────────────────────────────────────────────────────────────

    def load_global_models(self) -> None:
        """Deserialise the shared categoriser model.  Called once in lifespan."""
        _global_facade.load()
        logger.info(
            "Global categoriser loaded: %s", _global_facade.categoriser_loaded
        )

    # ── Categorisation ────────────────────────────────────────────────────────

    def categorise_description(
        self,
        db: Session,
        user_id: UUID,
        description: str,
    ) -> tuple[UUID | None, str, float]:
        """Return ``(category_id, label, confidence)`` for *description*.

        Resolution order:
        1. User-defined keyword rules (exact match).
        2. ML model prediction.
        3. Fallback: ``(None, "Uncategorised", 0.0)``.
        """
        # 1. Rule-based lookup
        rule = db.execute(
            select(UserTransactionRule)
            .where(
                UserTransactionRule.user_id == user_id,
                UserTransactionRule.keyword.ilike(f"%{description}%"),
            )
            .order_by(
                # prefer longer (more specific) keywords
            )
        ).scalars().first()

        if rule:
            return rule.category_id, "rule-based", 1.0

        # 2. ML prediction
        req = CategoriseRequest(
            transactions=[
                TransactionRecord(
                    date=datetime.now(tz=timezone.utc).date().isoformat(),
                    amount=1.0,
                    transaction_type="debit",
                    description=description,
                )
            ]
        )
        resp = _global_facade.categorise(req)
        prediction = resp.predictions[0]
        label = prediction.category
        confidence = float(prediction.confidence_score)

        if label == "Uncategorised":
            return None, label, 0.0

        category = db.execute(
            select(Category).where(
                Category.transaction_type == TransactionType.EXPENSE,
                Category.name.ilike(label),
                (Category.user_id == user_id) | (Category.user_id.is_(None)),
            )
        ).scalars().first()

        return (category.id if category else None), label, confidence

    def learn_from_user(
        self,
        db: Session,
        user_id: UUID,
        description: str,
        category_id: UUID,
    ) -> str | None:
        """Upsert a keyword rule extracted from *description*."""
        keyword = _extract_keyword(description)
        if not keyword:
            logger.warning("Could not extract keyword from: %r", description)
            return None

        existing = db.execute(
            select(UserTransactionRule).where(
                UserTransactionRule.user_id == user_id,
                UserTransactionRule.keyword == keyword,
            )
        ).scalar_one_or_none()

        if existing:
            if existing.category_id != category_id:
                existing.category_id = category_id
                db.add(existing)
        else:
            db.add(
                UserTransactionRule(
                    user_id=user_id,
                    keyword=keyword,
                    category_id=category_id,
                )
            )
        return keyword

    # ── Forecasting ───────────────────────────────────────────────────────────

    async def train_forecaster(self, db: Session, user_id: UUID) -> bool:
        """Train a per-user SARIMA model.

        - Returns immediately after spawning background work.
        - All heavy computation runs in a thread pool.
        - Updates ``UserMLState`` both before (TRAINING) and after (READY/FAILED).
        """
        # Fast sync work: query + mark training started
        transactions = _query_expense_transactions(db, user_id)
        if not transactions:
            logger.warning("No expense transactions found for user %s", user_id)
            return False

        records = _to_transaction_records(transactions)
        n_samples = len(records)
        model_path = _user_sarima_path(user_id)

        state = _get_or_create_ml_state(db, user_id)
        state.training_status = MLTrainingStatus.TRAINING
        state.n_training_samples = n_samples
        state.error_message = None
        db.add(state)
        db.commit()

        # Heavy work: run in thread pool
        def _run_training() -> bool:
            from fin_pilot_ml.forecasting.config import ForecastingConfig
            from fin_pilot_ml.forecasting.preprocessing import ExpensePreprocessor
            from fin_pilot_ml.forecasting.tuner import SarimaTuner
            from fin_pilot_ml.forecasting.models import ForecastModels
            from fin_pilot_ml.forecasting.persistence import ModelPersistence
            import pandas as pd

            # Build a new DB session for thread (sessions aren't thread-safe)
            from app.db.database import SESSION_LOCAL

            thread_db = SESSION_LOCAL()
            try:
                import warnings
                from statsmodels.tools.sm_exceptions import ConvergenceWarning
                warnings.filterwarnings("ignore", category=ConvergenceWarning)

                config = ForecastingConfig()
                preprocessor = ExpensePreprocessor()

                df = pd.DataFrame(
                    [
                        {
                            "Date": r.date,
                            "Amount": r.amount,
                            "Transaction Type": "Debit",
                            "Description": r.description,
                        }
                        for r in records
                    ]
                )

                try:
                    weekly_series, _ = preprocessor.preprocess(df)
                except ValueError as exc:
                    logger.warning("Preprocessing failed for user %s: %s", user_id, exc)
                    _update_ml_state(
                        thread_db, user_id, MLTrainingStatus.FAILED, str(exc)
                    )
                    return False

                if len(weekly_series) < 24:
                    msg = (
                        f"Insufficient data: {len(weekly_series)} weeks "
                        "(minimum 24 required)."
                    )
                    logger.warning(msg)
                    _update_ml_state(thread_db, user_id, MLTrainingStatus.FAILED, msg)
                    return False

                tuner = SarimaTuner(config)
                try:
                    best_order, best_seasonal_order = tuner.tune(weekly_series)
                except RuntimeError as exc:
                    _update_ml_state(
                        thread_db, user_id, MLTrainingStatus.FAILED, str(exc)
                    )
                    return False

                fitted = ForecastModels.train_sarima(
                    train_data=weekly_series,
                    order=best_order,
                    seasonal_order=best_seasonal_order,
                )

                model_path.parent.mkdir(parents=True, exist_ok=True)
                ModelPersistence.save(fitted, model_path)
                logger.info("SARIMA model saved to %s", model_path)

                # Write 12-week forecast to DB
                forecast_series = fitted.forecast(steps=12)
                import pandas as _pd
                from datetime import datetime as _dt, timezone as _tz
                points = [
                    (
                        _pd.Timestamp(idx)
                        .to_pydatetime()
                        .replace(tzinfo=_tz.utc),
                        max(0.0, float(val)),
                    )
                    for idx, val in zip(forecast_series.index, forecast_series.values)
                ]
                ForecastRepository(thread_db).save_batch(user_id, points)

                _update_ml_state(
                    thread_db,
                    user_id,
                    MLTrainingStatus.READY,
                    None,
                    str(model_path),
                )
                return True

            except Exception as exc:
                logger.exception("Training failed for user %s: %s", user_id, exc)
                _update_ml_state(
                    thread_db, user_id, MLTrainingStatus.FAILED, str(exc)
                )
                return False
            finally:
                thread_db.close()

        # Fire-and-forget: don't await, let it run in background
        asyncio.create_task(asyncio.to_thread(_run_training))
        return True

    def predict_weekly_expenses(
        self,
        user_id: UUID,
        n_weeks: int,
        db: Session,
    ) -> ForecastResponse:
        """Return an ML-module ``ForecastResponse`` for the given user.

        Falls back to cold-start response if the per-user model is not yet trained.
        """
        transactions = _query_expense_transactions(db, user_id)
        records = _to_transaction_records(transactions)

        user_facade = _load_user_facade(user_id)
        return user_facade.forecast(
            ForecastRequest(transactions=records, n_weeks=n_weeks)
        )

    # ── Recommendations ───────────────────────────────────────────────────────

    def get_ml_recommendations(
        self, db: Session, user_id: UUID
    ) -> RecommendationResponse:
        """Build a three-tier ``RecommendationResponse`` from the last 90 days."""
        from datetime import date

        transactions = _query_all_transactions(db, user_id)
        records = _to_transaction_records(transactions)

        income_total = sum(
            float(tx.amount)
            for tx in transactions
            if tx.transaction_type == TransactionType.INCOME
        )

        # Active budgets for this user → per-category limits
        budgets = list(
            db.execute(
                select(Budget)
                .where(Budget.user_id == user_id)
            ).scalars().all()
        )
        budget_limits: dict[str, float] = {}
        for b in budgets:
            if b.category:
                budget_limits[b.category.name] = float(b.limit_amount)

        user_facade = _load_user_facade(user_id)
        return user_facade.recommend(
            RecommendationRequest(
                transactions=records,
                income_total=income_total,
                budget_limits=budget_limits,
                reference_date=date.today().isoformat(),
            )
        )

    # ── Status ────────────────────────────────────────────────────────────────

    def get_training_status(self, db: Session, user_id: UUID) -> UserMLState | None:
        return db.execute(
            select(UserMLState).where(UserMLState.user_id == user_id)
        ).scalar_one_or_none()

    @property
    def categoriser_loaded(self) -> bool:
        return _global_facade.categoriser_loaded


# ── Module-level helpers ──────────────────────────────────────────────────────

def _extract_keyword(description: str) -> str:
    text = re.sub(r"\d+", "", description)
    text = re.sub(r"[^\w\s]", " ", text)
    words = [w.upper() for w in text.split() if len(w) > 1]
    return " ".join(words).strip()


def _update_ml_state(
    db: Session,
    user_id: UUID,
    status: MLTrainingStatus,
    error: str | None,
    model_path: str | None = None,
) -> None:
    state = db.execute(
        select(UserMLState).where(UserMLState.user_id == user_id)
    ).scalar_one_or_none()
    if state is None:
        state = UserMLState(user_id=user_id)
        db.add(state)
    state.training_status = status
    state.error_message = error
    if model_path is not None:
        state.sarima_model_path = model_path
    if status == MLTrainingStatus.READY:
        state.last_trained_at = datetime.now(tz=timezone.utc)
    db.commit()


# ── Singleton exposed to routes ───────────────────────────────────────────────

backend_ml_service = BackendMLService()
