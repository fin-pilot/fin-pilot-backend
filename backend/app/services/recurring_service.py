from sqlalchemy.orm import Session
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from backend.app.db.models import (
    RecurringTransaction,
    Transaction,
    RecurringInterval,
    Account,
)


def process_recurring_transactions(db: Session):
    today = date.today()

    due_subscriptions = (
        db.query(RecurringTransaction)
        .filter(
            RecurringTransaction.is_active == True,
            RecurringTransaction.next_date <= today,
        )
        .all()
    )

    for sub in due_subscriptions:
        new_transaction = Transaction(
            user_id=sub.user_id,
            account_id=sub.account_id,
            category_id=sub.category_id,
            description=f"[Subscription] {sub.description}",
            amount=sub.amount,
            type=sub.type,
            date=today,
        )
        db.add(new_transaction)

        account = db.query(Account).filter(Account.id == sub.account_id).first()
        if account:
            if sub.type == "expense":
                account.balance -= sub.amount
            else:
                account.balance += sub.amount

        if sub.interval == RecurringInterval.DAILY:
            sub.next_date += timedelta(days=1)
        elif sub.interval == RecurringInterval.WEEKLY:
            sub.next_date += timedelta(weeks=1)
        elif sub.interval == RecurringInterval.MONTHLY:
            sub.next_date += relativedelta(months=1)
        elif sub.interval == RecurringInterval.YEARLY:
            sub.next_date += relativedelta(years=1)

    db.commit()
    return len(due_subscriptions)
