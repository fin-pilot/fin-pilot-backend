from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import functions

from app.db.base import Base

class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class AccountType(str, enum.Enum):
    CASH = "cash"
    CARD = "card"


class RecurringInterval(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class MLTrainingStatus(str, enum.Enum):
    PENDING = "pending"
    TRAINING = "training"
    READY = "ready"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    hashed_password: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    full_name: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=functions.now(),
    )

    base_currency: Mapped[str] = mapped_column(
        String(3),
        default="UAH",
        nullable=False,
        server_default="UAH",
    )

    locale: Mapped[str] = mapped_column(
        String(2),
        default="uk",
        nullable=False,
        server_default="uk",
    )

    accounts: Mapped[list["Account"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    categories: Mapped[list["Category"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    budgets: Mapped[list["Budget"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    forecasts: Mapped[list["Forecast"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    rules: Mapped[list["UserTransactionRule"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    goals: Mapped[list["Goal"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    recurring_transactions: Mapped[list["RecurringTransaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    ml_state: Mapped[Optional["UserMLState"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType),
        default=AccountType.CARD,
        nullable=False,
    )

    balance: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2),
        default=0.0,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String,
        default="UAH",
        nullable=False,
    )

    owner: Mapped["User"] = relationship(
        back_populates="accounts",
    )

    transactions_out: Mapped[list["Transaction"]] = relationship(
        foreign_keys="Transaction.account_id",
        back_populates="account",
        cascade="all, delete-orphan",
    )

    transactions_in: Mapped[list["Transaction"]] = relationship(
        foreign_keys="Transaction.destination_account_id",
        back_populates="destination_account",
    )


class Category(Base):
    __tablename__ = "categories"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "name",
            "transaction_type",
            name="uq_user_category",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    slug: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType),
        nullable=False,
        index=True,
    )

    @property
    def type(self) -> TransactionType:
        return self.transaction_type

    @type.setter
    def type(self, value: TransactionType) -> None:
        self.transaction_type = value

    owner: Mapped[Optional["User"]] = relationship(
        back_populates="categories",
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="category",
    )

    budgets: Mapped[list["Budget"]] = relationship(
        back_populates="category",
    )

    rules: Mapped[list["UserTransactionRule"]] = relationship(
        back_populates="category",
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    destination_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    amount: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        String,
        index=True,
    )

    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType),
        default=TransactionType.EXPENSE,
        nullable=False,
        index=True,
    )

    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=functions.now(),
        nullable=False,
        index=True,
    )

    account: Mapped["Account"] = relationship(
        foreign_keys=[account_id],
        back_populates="transactions_out",
    )

    destination_account: Mapped[Optional["Account"]] = relationship(
        foreign_keys=[destination_account_id],
        back_populates="transactions_in",
    )

    category: Mapped[Optional["Category"]] = relationship(
        back_populates="transactions",
    )


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    limit_amount: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
    )

    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    owner: Mapped[Optional["User"]] = relationship(
        back_populates="budgets",
    )

    category: Mapped["Category"] = relationship(
        back_populates="budgets",
    )


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    target_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    predicted_amount: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
    )

    model_type: Mapped[str] = mapped_column(
        String,
        default="SARIMA",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=functions.now(),
    )

    user: Mapped["User"] = relationship(
        back_populates="forecasts",
    )


class UserTransactionRule(Base):
    __tablename__ = "user_transaction_rules"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "keyword",
            name="uq_user_keyword",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    keyword: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user: Mapped["User"] = relationship(
        back_populates="rules",
    )

    category: Mapped["Category"] = relationship(
        back_populates="rules",
    )


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    target_amount: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
    )

    current_amount: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2),
        default=0.0,
        nullable=False,
    )

    deadline: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=functions.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=functions.now(),
        onupdate=functions.now(),
    )

    user: Mapped["User"] = relationship(
        back_populates="goals",
    )


class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    amount: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
    )

    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType),
        default=TransactionType.EXPENSE,
        nullable=False,
    )

    @property
    def type(self) -> TransactionType:
        return self.transaction_type

    @type.setter
    def type(self, value: TransactionType) -> None:
        self.transaction_type = value

    interval: Mapped[RecurringInterval] = mapped_column(
        Enum(RecurringInterval),
        nullable=False,
    )

    start_date: Mapped[date] = mapped_column(
        Date,
        default=date.today,
        nullable=False,
    )

    next_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        back_populates="recurring_transactions",
    )

    account: Mapped["Account"] = relationship()

    category: Mapped[Optional["Category"]] = relationship()


class UserMLState(Base):
    """Tracks per-user ML model training state and artifact paths."""

    __tablename__ = "user_ml_states"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    training_status: Mapped[MLTrainingStatus] = mapped_column(
        Enum(MLTrainingStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=MLTrainingStatus.PENDING,
        nullable=False,
    )

    sarima_model_path: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
    )

    n_training_samples: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    last_trained_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
    )

    owner: Mapped["User"] = relationship(
        back_populates="ml_state",
    )


class ExchangeRate(Base):
    """Daily exchange rate snapshot.

    Convention: ``rate`` is the number of ``base_currency`` units that equal
    one unit of ``target_currency``.
    Example: base=UAH, target=USD, rate=41.50  →  1 USD = 41.50 UAH.
    """

    __tablename__ = "exchange_rates"

    __table_args__ = (
        UniqueConstraint(
            "base_currency",
            "target_currency",
            "rate_date",
            name="uq_exchange_rate_daily",
        ),
        Index("ix_exchange_rates_lookup", "base_currency", "target_currency", "rate_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    base_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    target_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    rate: Mapped[float] = mapped_column(
        Numeric(precision=18, scale=6),
        nullable=False,
    )

    rate_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(32),
        default="NBU",
        nullable=False,
    )
