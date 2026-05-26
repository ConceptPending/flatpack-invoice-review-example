"""CSV parser + auto-mapping tests.

Carried over from the Flatpack's FLATPACK:TEST_CASES — same names,
same intent, Python idioms. See reference/promotion-plan.md "Test cases
to carry over" for the mapping.
"""

from app.services.csv_parser import (
    SCHEMA_FIELDS,
    apply_mapping,
    auto_map,
    parse_csv,
    to_csv,
)


def test_parse_csv_handles_quoted_commas():
    """Carried over: 'parseCSV handles quoted commas'."""
    rows = parse_csv('a,b,c\n"hello, world",2,3\n')
    assert len(rows) == 2
    assert rows[1] == ["hello, world", "2", "3"]


def test_parse_csv_handles_escaped_quotes():
    """Carried over: 'parseCSV handles escaped quotes'."""
    rows = parse_csv('a\n"she said ""hi"""\n')
    assert rows[1] == ['she said "hi"']


def test_to_csv_round_trip_preserves_embedded_commas():
    """Carried over: 'toCSV round-trip preserves embedded commas'."""
    out = to_csv([["a", "b"], ["x,y", "z"]])
    back = parse_csv(out)
    assert back[1][0] == "x,y"


def test_auto_map_picks_vendor_and_ccy_from_supplier_invoice_export():
    """Carried over: 'autoMap picks Vendor for supplier_name and
    CCY for currency'."""
    mapping = auto_map(["Vendor", "Invoice Date", "Invoice No.", "Total", "CCY"])
    assert mapping["supplier_name"] == "Vendor"
    assert mapping["currency"] == "CCY"
    assert mapping["amount"] == "Total"


def test_apply_mapping_projects_to_schema_fields():
    """Sanity check: apply_mapping returns dicts with all SCHEMA_FIELDS keys."""
    headers = ["Vendor", "Invoice Date", "Invoice No.", "Total", "CCY"]
    rows = [["Acme Ltd", "2026-01-15", "INV-001", "1200.50", "GBP"]]
    mapping = auto_map(headers)
    out = apply_mapping(rows, headers, mapping)
    assert len(out) == 1
    assert set(out[0].keys()) == set(SCHEMA_FIELDS)
    assert out[0]["supplier_name"] == "Acme Ltd"
    assert out[0]["currency"] == "GBP"
