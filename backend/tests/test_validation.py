"""Row validator tests.

Carried over from the Flatpack's FLATPACK:TEST_CASES. One deliberate
divergence: the 'unknown currency is a warning, not an error' test
from the Flatpack becomes 'unknown currency is an error' here, per
the strengthened rule in reference/decisions.md decision B.
"""

import datetime as dt

from app.services.validation import normalise_currency, validate_row


def _base_row(**overrides) -> dict:
    row = {
        "supplier_name": "Acme Ltd",
        "invoice_date": "2026-01-15",
        "invoice_number": "INV-001",
        "amount": "100.00",
        "currency": "GBP",
    }
    row.update(overrides)
    return row


def test_validate_row_flags_future_invoice_date():
    """Carried over: 'validateRow flags future invoice date'."""
    future = (dt.date.today() + dt.timedelta(days=365)).isoformat()
    errs = validate_row(_base_row(invoice_date=future))
    assert any("future" in e.lower() for e in errs)


def test_amount_must_be_greater_than_zero():
    """Carried over: 'amount must be > 0'."""
    errs = validate_row(_base_row(amount="0"))
    assert any("greater than zero" in e.lower() for e in errs)

    errs_neg = validate_row(_base_row(amount="-5"))
    assert any("greater than zero" in e.lower() for e in errs_neg)


def test_currency_normalisation_uppercases_and_trims():
    """Carried over: 'currency normalisation lowercases gbp → GBP'."""
    assert normalise_currency("  gbp ") == "GBP"
    assert normalise_currency("eur") == "EUR"


def test_unknown_currency_is_an_error_strengthened_from_flatpack():
    """Strengthened from the Flatpack: out-of-list currency was a
    warning that defaulted to GBP; here it is an error.

    Justification in reference/decisions.md decision B."""
    errs = validate_row(_base_row(currency="JPY"))
    assert any("outside" in e.lower() for e in errs)


def test_missing_required_fields_each_produce_an_error():
    errs = validate_row(_base_row(supplier_name=""))
    assert any("supplier name missing" in e.lower() for e in errs)

    errs2 = validate_row(_base_row(invoice_number=""))
    assert any("invoice number missing" in e.lower() for e in errs2)

    errs3 = validate_row(_base_row(amount=""))
    assert any("amount missing" in e.lower() for e in errs3)


def test_valid_row_produces_no_errors():
    errs = validate_row(_base_row())
    assert errs == []
