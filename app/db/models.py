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
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import functions


class Base(DeclarativeBase):
    pass


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

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
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

    owner: Mapped["User"] = relationship(
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
