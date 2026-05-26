"""CSV parsing — carries over from the Flatpack's CORE_LOGIC.

The Flatpack's parseCSV() is a hand-rolled RFC-4180 minimal parser. We
use Python's built-in csv module here instead — semantically equivalent
for the row shapes we care about (quotes, embedded commas, CRLF), and
better-tested by the standard library.

Pure functions: no DB, no app state.
"""

from __future__ import annotations

import csv
from io import StringIO

# Conventional column-mapping synonyms carried over verbatim from the
# Flatpack's autoMap() function. Each manifest field name maps to a
# list of normalised header tokens that should be auto-recognised.
SYNONYMS: dict[str, list[str]] = {
    "supplier_name":  ["supplier", "vendor", "company", "merchant"],
    "invoice_date":   ["date", "issued", "invoicedate", "issuedate"],
    "invoice_number": ["invoice", "invoicenumber", "invoiceno", "invoice_id", "number", "ref"],
    "amount":         ["amount", "total", "gross", "value", "amt"],
    "currency":       ["currency", "ccy", "cur"],
}

SCHEMA_FIELDS = list(SYNONYMS.keys())


def _norm(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


def parse_csv(text: str) -> list[list[str]]:
    """Parse a CSV string into a list of rows. The first row is the header.

    Compatible with the Flatpack's parseCSV(): handles quoted fields,
    embedded commas, embedded newlines, escaped quotes (RFC 4180-ish).
    """
    if not text:
        return []
    reader = csv.reader(StringIO(text))
    rows = [row for row in reader]
    # Drop trailing all-empty rows (matches the Flatpack's behaviour).
    while rows and all(cell == "" for cell in rows[-1]):
        rows.pop()
    return rows


def auto_map(headers: list[str]) -> dict[str, str]:
    """Suggest a mapping from schema field → header in this file.

    Carries over the Flatpack's autoMap() with the supplier-invoice
    synonym table. Best-effort; the reviewer can override.
    """
    mapping: dict[str, str] = {}
    norm_headers = {_norm(h): h for h in headers}
    for field in SCHEMA_FIELDS:
        want = _norm(field)
        synonyms = SYNONYMS[field]
        found = ""
        # Exact normalised match wins.
        if want in norm_headers:
            found = norm_headers[want]
        else:
            # Then synonym matches.
            for syn in synonyms:
                if syn in norm_headers:
                    found = norm_headers[syn]
                    break
            # Then substring contains.
            if not found:
                for nh, original in norm_headers.items():
                    if any(syn in nh for syn in synonyms):
                        found = original
                        break
        mapping[field] = found
    return mapping


def apply_mapping(
    raw_rows: list[list[str]],
    headers: list[str],
    mapping: dict[str, str],
) -> list[dict[str, str]]:
    """Project raw CSV rows into dicts keyed by manifest field names."""
    idx: dict[str, int] = {}
    for field, header in mapping.items():
        idx[field] = headers.index(header) if header and header in headers else -1
    out = []
    for row in raw_rows:
        obj: dict[str, str] = {}
        for field in SCHEMA_FIELDS:
            i = idx[field]
            obj[field] = (row[i] if 0 <= i < len(row) else "") or ""
        out.append(obj)
    return out


def to_csv(rows: list[list[object]]) -> str:
    """Serialise rows back to CSV. Inverse of parse_csv(); preserves the
    Flatpack's toCSV() behaviour of quoting cells with embedded commas,
    quotes, or newlines."""
    buf = StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerows(rows)
    return buf.getvalue()
