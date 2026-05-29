from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.core.exceptions import NotFoundError, ValidationError
from backend.app.db.models import Transaction, TransactionType
from backend.app.repositories.account_repository import AccountRepository
from backend.app.repositories.category_repository import CategoryRepository
from backend.app.repositories.transaction_repository import (
    TransactionRepository,
)
from backend.app.schemas.transaction import (
    TransactionCreate,
    TransactionImportResult,
    TransactionUpdate,
)
from backend.app.services.ledger_service import LedgerService
from backend.app.services.ml_service import ml_service


class TransactionService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = TransactionRepository(db)
        self._accounts = AccountRepository(db)
        self._categories = CategoryRepository(db)
        self._ledger = LedgerService(db)

    def list_transactions(
        self,
        user_id: UUID,
        *,
        skip: int,
        limit: int,
        start_date: date | None,
        end_date: date | None,
        account_id: UUID | None,
        category_id: UUID | None,
        transaction_type: str | None,
    ) -> list[Transaction]:
        parsed_type = None
        if transaction_type:
            parsed_type = self._parse_transaction_type(transaction_type)

        return self._repo.list_for_user(
            user_id,
            skip=skip,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
            category_id=category_id,
            transaction_type=parsed_type,
        )

    def get_transaction(self, user_id: UUID, trans_id: UUID) -> Transaction:
        transaction = self._repo.get_for_user(trans_id, user_id)
        if not transaction:
            raise NotFoundError("Transaction not found or access denied")
        return transaction

    def create_transaction(
        self,
        user_id: UUID,
        trans_in: TransactionCreate,
    ) -> Transaction:
        account = self._accounts.get_by_id_for_user(
            trans_in.account_id, user_id
        )
        if not account:
            raise NotFoundError("Account not found or access denied")

        category = self._categories.get_for_user_or_global(
            trans_in.category_id,
            user_id,
        )
        if not category:
            raise ValidationError("Invalid category ID or access denied")

        dest_account = None
        if trans_in.transaction_type == TransactionType.TRANSFER:
            if trans_in.destination_account_id is None:
                raise ValidationError(
                    "Destination account required for transfer."
                )
            dest_account = self._accounts.get_by_id_for_user(
                trans_in.destination_account_id,
                user_id,
            )
            if not dest_account:
                raise NotFoundError("Destination account not found")

        data = trans_in.model_dump()
        new_transaction = Transaction(**data)

        with self._db.begin():
            self._ledger.apply_transaction(
                account,
                dest_account,
                trans_in.amount,
                trans_in.transaction_type,
            )
            self._repo.add(new_transaction)

            if (
                new_transaction.description
                and new_transaction.category_id is not None
                and new_transaction.transaction_type == TransactionType.EXPENSE
            ):
                ml_service.learn_from_user(
                    self._db,
                    user_id,
                    new_transaction.description,
                    new_transaction.category_id,
                )

        self._db.refresh(new_transaction)
        return new_transaction

    def update_transaction(
        self,
        user_id: UUID,
        trans_id: UUID,
        trans_in: TransactionUpdate,
    ) -> Transaction:
        trans = self._repo.get_for_user(trans_id, user_id)
        if not trans:
            raise NotFoundError("Transaction not found or access denied")

        category_changed = (
            trans_in.category_id is not None
            and trans_in.category_id != trans.category_id
        )

        category_id: UUID | None = trans_in.category_id
        if category_id is not None:
            category = self._categories.get_for_user_or_global(
                category_id,
                user_id,
            )
            if not category:
                raise ValidationError("Invalid category ID")

        update_data = trans_in.model_dump(exclude_unset=True)
        if update_data.get("amount") is None:
            update_data.pop("amount", None)
        amount_changed = (
            trans_in.amount is not None and trans_in.amount != trans.amount
        )

        with self._db.begin():
            if amount_changed:
                self._ledger.update_transaction(
                    trans.account,
                    trans.destination_account,
                    trans.amount,
                    update_data["amount"],
                    trans.transaction_type,
                )

            for key, value in update_data.items():
                setattr(trans, key, value)

            if (
                category_changed
                and trans.description
                and trans.category_id is not None
                and trans.transaction_type == TransactionType.EXPENSE
            ):
                ml_service.learn_from_user(
                    self._db,
                    user_id,
                    trans.description,
                    trans.category_id,
                )

        self._db.refresh(trans)
        return trans

    def delete_transaction(self, user_id: UUID, trans_id: UUID) -> None:
        trans = self._repo.get_for_user(trans_id, user_id)
        if not trans:
            raise NotFoundError("Transaction not found")

        with self._db.begin():
            self._ledger.reverse_transaction(
                trans.account,
                trans.destination_account,
                trans.amount,
                trans.transaction_type,
            )
            self._repo.delete(trans)

    def export_transactions(self, user_id: UUID) -> Iterable[str]:
        rows = self._repo.list_for_user_export(user_id)

        def iter_csv() -> Iterable[str]:
            output = io.StringIO(newline="")
            writer = csv.writer(output)

            writer.writerow(
                [
                    "id",
                    "account_id",
                    "destination_account_id",
                    "category_id",
                    "amount",
                    "description",
                    "transaction_type",
                    "transaction_date",
                ]
            )
            yield output.getvalue()

            for row in rows:
                output.seek(0)
                output.truncate(0)
                writer.writerow(
                    [
                        row.id,
                        row.account_id,
                        row.destination_account_id or "",
                        row.category_id or "",
                        row.amount,
                        row.description or "",
                        row.transaction_type.value,
                        row.transaction_date.isoformat(),
                    ]
                )
                yield output.getvalue()

        return iter_csv()

    def import_transactions(
        self,
        user_id: UUID,
        *,
        file_bytes: bytes,
        default_account_id: UUID,
    ) -> TransactionImportResult:
        default_account = self._accounts.get_by_id_for_user(
            default_account_id,
            user_id,
        )
        if not default_account:
            raise NotFoundError("Default account not found")

        try:
            text = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationError("CSV must be UTF-8 encoded") from exc

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValidationError("Empty CSV")

        created = 0
        skipped = 0
        errors: list[str] = []

        for i, row in enumerate(reader, start=2):
            try:
                acc_raw = (row.get("account_id") or "").strip()
                account_id = UUID(acc_raw) if acc_raw else default_account_id
                account = self._accounts.get_by_id_for_user(
                    account_id,
                    user_id,
                )
                if not account:
                    errors.append(f"Line {i}: unknown account_id")
                    skipped += 1
                    continue

                amount = float((row.get("amount") or "").strip())
                desc = (row.get("description") or "").strip() or None
                tx_type = self._parse_transaction_type(
                    row.get("transaction_type")
                )

                dest_account = None
                dest_raw = (row.get("destination_account_id") or "").strip()
                if tx_type == TransactionType.TRANSFER:
                    if not dest_raw:
                        errors.append(f"Line {i}: transfer needs destination")
                        skipped += 1
                        continue
                    did = UUID(dest_raw)
                    dest_account = self._accounts.get_by_id_for_user(
                        did, user_id
                    )
                    if not dest_account:
                        errors.append(f"Line {i}: bad destination_account_id")
                        skipped += 1
                        continue

                cat_id = self._resolve_category_id(
                    row,
                    user_id,
                    tx_type,
                    desc,
                )
                if not cat_id:
                    errors.append(
                        f"Line {i}: Global fallback category 'Other' is missing"
                    )
                    skipped += 1
                    continue

                tdate_raw = (row.get("transaction_date") or "").strip()
                if tdate_raw:
                    tdate = datetime.fromisoformat(
                        tdate_raw.replace("Z", "+00:00")
                    )
                else:
                    tdate = datetime.now().astimezone()

                with self._db.begin():
                    self._ledger.apply_transaction(
                        account,
                        dest_account,
                        amount,
                        tx_type,
                    )

                    new_tx = Transaction(
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
                    self._repo.add(new_tx)

                    if desc and tx_type == TransactionType.EXPENSE:
                        ml_service.learn_from_user(
                            self._db,
                            user_id,
                            desc,
                            cat_id,
                        )

                created += 1
            except (ValueError, TypeError, ValidationError) as exc:
                errors.append(f"Line {i}: {exc}")
                skipped += 1

        return TransactionImportResult(
            created=created,
            skipped=skipped,
            errors=errors[:50],
        )

    def _resolve_category_id(
        self,
        row: dict[str, str | None],
        user_id: UUID,
        tx_type: TransactionType,
        desc: str | None,
    ) -> UUID | None:
        cname = (row.get("category_name") or "").strip()
        if cname:
            category = self._categories.find_by_name_for_user_or_global(
                cname,
                user_id,
                tx_type,
            )
            if category:
                return category.id

        if desc and tx_type == TransactionType.EXPENSE:
            cat_id, _ = ml_service.categorize_transaction_description(
                self._db,
                user_id,
                desc,
            )
            if cat_id:
                return cat_id

        fallback = self._categories.get_global_by_name_and_type(
            "Other",
            tx_type,
        )
        if fallback:
            return fallback.id
        return None

    @staticmethod
    def _parse_transaction_type(raw: str | None) -> TransactionType:
        if not raw or not raw.strip():
            return TransactionType.EXPENSE
        key = raw.strip().lower()
        mapping = {
            "income": TransactionType.INCOME,
            "expense": TransactionType.EXPENSE,
            "transfer": TransactionType.TRANSFER,
        }
        if key not in mapping:
            raise ValidationError(f"Unknown transaction_type: {raw!r}")
        return mapping[key]
