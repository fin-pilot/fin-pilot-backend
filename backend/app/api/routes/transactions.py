from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_categorizer, get_current_user
from app.db.database import get_db
from app.db.models import Account, Transaction, TransactionType, User
from app.ml.nlp_categorizer import TransactionCategorizer
from app.schemas.transaction import (
    PredictCategoryRequest,
    PredictCategoryResponse,
    TransactionCreate,
    TransactionImportResult,
    TransactionResponse,
    TransactionUpdate,
)
from app.services.category_resolution import resolve_category_for_label

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _apply_transaction_balance(
    account: Account,
    dest_account: Account | None,
    amount: float,
    transaction_type: TransactionType,
    *,
    reverse: bool = False,
) -> None:
    sign = -1.0 if reverse else 1.0
    if transaction_type == TransactionType.INCOME:
        account.balance += sign * amount
    elif transaction_type == TransactionType.EXPENSE:
        account.balance -= sign * amount
    elif transaction_type == TransactionType.TRANSFER:
        if dest_account is None:
            raise HTTPException(
                status_code=400,
                detail="Destination account required for transfer.",
            )
        account.balance -= sign * amount
        dest_account.balance += sign * amount


def _parse_tx_type(raw: str | None) -> TransactionType:
    if not raw or not raw.strip():
        return TransactionType.EXPENSE
    key = raw.strip().lower()
    mapping = {
        "income": TransactionType.INCOME,
        "expense": TransactionType.EXPENSE,
        "transfer": TransactionType.TRANSFER,
    }
    if key not in mapping:
        raise ValueError(f"Unknown transaction_type: {raw!r}")
    return mapping[key]


@router.get("/", response_model=List[TransactionResponse])
def get_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    return (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == current_user.id)
        .order_by(Transaction.transaction_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.post(
    "/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED
)
def create_transaction(
    trans_in: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = (
        db.query(Account)
        .filter(
            Account.id == trans_in.account_id,
            Account.user_id == current_user.id,
        )
        .first()
    )
    if not account:
        raise HTTPException(
            status_code=404, detail="Account not found or access denied"
        )

    dest_account: Account | None = None
    if trans_in.transaction_type == TransactionType.TRANSFER:
        dest_account = (
            db.query(Account)
            .filter(
                Account.id == trans_in.destination_account_id,
                Account.user_id == current_user.id,
            )
            .first()
        )
        if not dest_account:
            raise HTTPException(
                status_code=404, detail="Destination account not found"
            )

    data = trans_in.model_dump()
    if (
        data.get("category_id") is None
        and trans_in.transaction_type == TransactionType.EXPENSE
        and trans_in.description
    ):
        categorizer = get_categorizer()
        if categorizer.pipeline is not None:
            label = categorizer.predict(trans_in.description)
            resolved = resolve_category_for_label(
                db,
                current_user.id,
                label,
                TransactionType.EXPENSE,
            )
            if resolved:
                data["category_id"] = resolved.id

    _apply_transaction_balance(
        account,
        dest_account,
        trans_in.amount,
        trans_in.transaction_type,
    )

    new_transaction = Transaction(**data)
    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)
    return new_transaction


@router.get("/export")
def export_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == current_user.id)
        .order_by(Transaction.transaction_date.desc())
        .all()
    )

    def iter_csv():
        yield (
            "id,account_id,destination_account_id,category_id,amount,"
            "description,transaction_type,transaction_date\n"
        )
        for t in rows:
            desc = (t.description or "").replace(",", ";").replace("\n", " ")
            yield (
                f"{t.id},{t.account_id},"
                f"{t.destination_account_id or ''},"
                f"{t.category_id or ''},"
                f"{t.amount},{desc},"
                f"{t.transaction_type.value},"
                f"{t.transaction_date.isoformat()}\n"
            )

    return StreamingResponse(
        iter_csv(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=transactions.csv",
        },
    )


@router.post("/import", response_model=TransactionImportResult)
async def import_transactions_csv(
    file: UploadFile = File(...),
    default_account_id: UUID = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    default_account = (
        db.query(Account)
        .filter(
            Account.id == default_account_id,
            Account.user_id == current_user.id,
        )
        .first()
    )
    if not default_account:
        raise HTTPException(status_code=404, detail="Default account not found")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="CSV must be UTF-8 encoded"
        ) from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Empty CSV")

    created = 0
    skipped = 0
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):
        try:
            acc_raw = (row.get("account_id") or "").strip()
            account_id = UUID(acc_raw) if acc_raw else default_account_id
            account = (
                db.query(Account)
                .filter(
                    Account.id == account_id,
                    Account.user_id == current_user.id,
                )
                .first()
            )
            if not account:
                errors.append(f"Line {i}: unknown account_id")
                skipped += 1
                continue

            amount = float((row.get("amount") or "").strip())
            desc = (row.get("description") or "").strip() or None
            tx_type = _parse_tx_type(row.get("transaction_type"))

            dest_account: Account | None = None
            dest_raw = (row.get("destination_account_id") or "").strip()
            if tx_type == TransactionType.TRANSFER:
                if not dest_raw:
                    errors.append(f"Line {i}: transfer needs destination")
                    skipped += 1
                    continue
                did = UUID(dest_raw)
                dest_account = (
                    db.query(Account)
                    .filter(
                        Account.id == did,
                        Account.user_id == current_user.id,
                    )
                    .first()
                )
                if not dest_account:
                    errors.append(f"Line {i}: bad destination_account_id")
                    skipped += 1
                    continue

            cat_id: UUID | None = None
            cname = (row.get("category_name") or "").strip()
            if cname:
                cat = resolve_category_for_label(
                    db, current_user.id, cname, tx_type
                )
                if cat:
                    cat_id = cat.id

            tdate_raw = (row.get("transaction_date") or "").strip()
            if tdate_raw:
                tdate = datetime.fromisoformat(tdate_raw.replace("Z", "+00:00"))
            else:
                tdate = datetime.now().astimezone()

            _apply_transaction_balance(
                account,
                dest_account,
                amount,
                tx_type,
            )

            db.add(
                Transaction(
                    account_id=account.id,
                    destination_account_id=(
                        dest_account.id if dest_account else None
                    ),
                    category_id=cat_id,
                    amount=amount,
                    description=desc,
                    transaction_type=tx_type,
                    transaction_date=tdate,
                )
            )
            db.commit()
            created += 1
        except (ValueError, TypeError) as exc:
            db.rollback()
            errors.append(f"Line {i}: {exc}")
            skipped += 1

    return TransactionImportResult(
        created=created, skipped=skipped, errors=errors[:50]
    )


@router.post("/predict-category", response_model=PredictCategoryResponse)
def predict_transaction_category(
    request: PredictCategoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    categorizer: TransactionCategorizer = Depends(get_categorizer),
):
    if categorizer.pipeline is None:
        raise HTTPException(
            status_code=503, detail="ML model is not trained or loaded yet."
        )

    label = categorizer.predict(request.description)
    resolved = resolve_category_for_label(
        db,
        current_user.id,
        label,
        TransactionType.EXPENSE,
    )
    if resolved:
        return PredictCategoryResponse(
            predicted_category_id=resolved.id,
            predicted_label=str(label),
            confidence_score=1.0,
            message="Category matched by name for this user or global catalog.",
        )
    return PredictCategoryResponse(
        predicted_category_id=None,
        predicted_label=str(label),
        confidence_score=0.5,
        message=(
            "Model predicted a label, but no matching expense category exists. "
            "Create a category with this name or map synonyms in training data."
        ),
    )


@router.get("/{trans_id}", response_model=TransactionResponse)
def get_transaction(
    trans_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trans = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Transaction.id == trans_id, Account.user_id == current_user.id)
        .first()
    )

    if not trans:
        raise HTTPException(
            status_code=404, detail="Transaction not found or access denied"
        )

    return trans


@router.put("/{trans_id}", response_model=TransactionResponse)
def update_transaction(
    trans_id: UUID,
    trans_in: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trans = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Transaction.id == trans_id, Account.user_id == current_user.id)
        .first()
    )

    if not trans:
        raise HTTPException(
            status_code=404, detail="Transaction not found or access denied"
        )

    if trans_in.amount is not None and trans_in.amount != trans.amount:
        amount_difference = trans_in.amount - trans.amount
        account = trans.account

        if trans.transaction_type == TransactionType.INCOME:
            account.balance += amount_difference

        elif trans.transaction_type == TransactionType.EXPENSE:
            account.balance -= amount_difference

        elif trans.transaction_type == TransactionType.TRANSFER:
            dest_account = trans.destination_account
            if not dest_account:
                raise HTTPException(
                    status_code=500,
                    detail="Destination account missing for transfer",
                )

            account.balance -= amount_difference
            dest_account.balance += amount_difference

    update_data = trans_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(trans, key, value)

    db.commit()
    db.refresh(trans)

    return trans


@router.delete("/{trans_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    trans_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trans = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Transaction.id == trans_id, Account.user_id == current_user.id)
        .first()
    )

    if not trans:
        raise HTTPException(status_code=404, detail="Transaction not found")

    account = trans.account
    _apply_transaction_balance(
        account,
        trans.destination_account,
        trans.amount,
        trans.transaction_type,
        reverse=True,
    )

    db.delete(trans)
    db.commit()
    return None
