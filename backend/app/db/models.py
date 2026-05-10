import enum
import uuid
from sqlalchemy import (
    Column,
    String,
    Float,
    DateTime,
    ForeignKey,
    Enum,
    Uuid,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import functions
from app.db.database import Base


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class AccountType(str, enum.Enum):
    CASH = "cash"
    CARD = "card"


class User(Base):
    __tablename__ = "users"

    id = Column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=functions.now())

    accounts = relationship(
        "Account", back_populates="owner", cascade="all, delete-orphan"
    )
    categories = relationship(
        "Category", back_populates="owner", cascade="all, delete-orphan"
    )
    budgets = relationship(
        "Budget", back_populates="owner", cascade="all, delete-orphan"
    )
    forecasts = relationship(
        "Forecast", back_populates="user", cascade="all, delete-orphan"
    )


class Account(Base):
    __tablename__ = "accounts"

    id = Column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String, nullable=False)
    account_type = Column(Enum(AccountType), default=AccountType.CARD)
    balance = Column(Float, default=0.0)
    currency = Column(String, default="UAH")

    owner = relationship("User", back_populates="accounts")
    transactions_out = relationship(
        "Transaction",
        foreign_keys="[Transaction.account_id]",
        back_populates="account",
    )
    transactions_in = relationship(
        "Transaction",
        foreign_keys="[Transaction.destination_account_id]",
        back_populates="destination_account",
    )


class Category(Base):
    __tablename__ = "categories"

    id = Column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    name = Column(String, nullable=False)
    type = Column(Enum(TransactionType), nullable=False)

    owner = relationship("User", back_populates="categories")
    transactions = relationship("Transaction", back_populates="category")
    budgets = relationship("Budget", back_populates="category")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    account_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    destination_account_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=True,
    )
    category_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    amount = Column(Float, nullable=False)
    description = Column(String, index=True)
    transaction_type = Column(
        Enum(TransactionType), default=TransactionType.EXPENSE, nullable=False
    )

    transaction_date = Column(
        DateTime(timezone=True), server_default=functions.now(), nullable=False
    )

    account = relationship(
        "Account", foreign_keys=[account_id], back_populates="transactions_out"
    )
    destination_account = relationship(
        "Account",
        foreign_keys=[destination_account_id],
        back_populates="transactions_in",
    )
    category = relationship("Category", back_populates="transactions")


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
    )

    limit_amount = Column(Float, nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)

    owner = relationship("User", back_populates="budgets")
    category = relationship("Category", back_populates="budgets")


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    target_date = Column(DateTime(timezone=True), nullable=False)
    predicted_amount = Column(Float, nullable=False)

    model_type = Column(String, default="SARIMA")
    created_at = Column(DateTime(timezone=True), server_default=functions.now())

    user = relationship("User", back_populates="forecasts")
