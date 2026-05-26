"""Row validation. Carries over the Flatpack's validateRow() rules.

Pure functions: input dict in, list[str] of reasons out. No DB access.

The currency rule is **stricter** here than in the Flatpack — see
reference/decisions.md decision B. Out-of-list currency produces a
validation error rather than a warning-with-default. The Flatpack's
"warning, defaults to GBP" semantics had bitten the team once; the
team chose to surface the row for review instead.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation

ALLOWED_CURRENCIES = ("GBP", "EUR", "USD")


def normalise_currency(v: str | None) -> str:
    """Carries over normaliseCurrency() from the Flatpack."""
    if v is None:
        return ""
    return str(v).strip().upper()


def validate_row(row: dict[str, str]) -> list[str]:
    """Apply the manifest's validation rules to a single row.

    Returns a list of plain-English reasons the row failed. Empty list
    means the row is valid. The text of each reason intentionally
    mirrors the Flatpack's validateRow() output so a side-by-side
    comparison reads cleanly.
    """
    errs: list[str] = []

    # Required fields.
    supplier_name = (row.get("supplier_name") or "").strip()
    invoice_number = (row.get("invoice_number") or "").strip()
    raw_amount = (row.get("amount") or "").strip()
    raw_date = (row.get("invoice_date") or "").strip()

    if not supplier_name:
        errs.append("Supplier name missing")
    if not invoice_number:
        errs.append("Invoice number missing")
    if not raw_amount:
        errs.append("Amount missing")
    if not raw_date:
        errs.append("Invoice date missing")

    # Amount: must be a number, and > 0 per the Flatpack manifest.
    if raw_amount:
        try:
            n = Decimal(raw_amount)
        except (InvalidOperation, ValueError):
            errs.append("Amount not a number")
        else:
            if n <= 0:
                errs.append("Amount must be greater than zero")

    # Invoice date: must be a valid date, and not in the future.
    if raw_date:
        parsed = _try_parse_date(raw_date)
        if parsed is None:
            errs.append("Invoice date not a valid date")
        else:
            if parsed > dt.date.today():
                errs.append("Invoice date is in the future")

    # Currency: stricter than the Flatpack — out-of-list is an error.
    # See reference/decisions.md decision B.
    raw_currency = row.get("currency")
    if raw_currency:
        c = normalise_currency(raw_currency)
        if c and c not in ALLOWED_CURRENCIES:
            errs.append(
                f'Currency "{raw_currency}" outside '
                f"{'/'.join(ALLOWED_CURRENCIES)} — fix the row"
            )

    return errs


def _try_parse_date(s: str) -> dt.date | None:
    """Permissive date parser. Tries ISO first, then a couple of common
    fallbacks. Anything we can't parse is None."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None
