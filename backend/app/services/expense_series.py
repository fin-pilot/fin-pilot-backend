import pandas as pd
from sqlalchemy.orm import Session
from uuid import UUID
from app.db.models import Transaction, Account, TransactionType


def daily_expense_dataframe(db: Session, user_id: UUID) -> pd.DataFrame:
    transactions = (
        db.query(Transaction)
        .join(Account)
        .filter(
            Account.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
        )
        .all()
    )

    if not transactions:
        return pd.DataFrame(columns=["date", "amount"])

    data = [
        {"date": t.transaction_date.date(), "amount": t.amount}
        for t in transactions
    ]
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])

    df = df.groupby("date")["amount"].sum().reset_index()

    df.set_index("date", inplace=True)
    df = df.asfreq("D", fill_value=0.0).reset_index()

    return df
