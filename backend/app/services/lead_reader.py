"""Fill the "New internal lead" form from a file (Excel .xlsx or CSV).

Nothing is saved here: the file is read, its values are matched to the form's fields (the ones in
`InternalLeadIn`), and the person checks them and clicks Save as usual. Columns we have no field for come
back as `extra`, so the screen can say they were not saved.

Two layouts are understood:
  - a table: the first row names the columns, each next row is one lead (the person picks the row);
  - a card: column A names the field, column B holds the value ("Phone | +91 98480 12345").

Safety: the file must pass `file_check` (real, whole, no zip bomb); only cell values are read, never formulas
(`data_only`); at most MAX_ROWS rows, MAX_COLS columns and MAX_CELL characters per cell are read.
"""
import csv
import io
import re
from datetime import date, datetime

from openpyxl import load_workbook

from app.core.errors import AppError
from app.schemas.lead import InternalLeadIn
from app.services import file_check

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 50  # leads shown to pick from (one file fills one lead)
MAX_COLS = 50
MAX_CELL = 500  # characters kept from a cell we have no field for

# Our field (a field of InternalLeadIn) -> column names people actually use. Compared after _norm():
# lower case, punctuation turned into spaces ("Mobile No." -> "mobile no").
ALIASES = {
    "name": ("name", "contact", "contact name", "contact person", "person", "customer", "customer name",
             "buyer name", "full name", "client name"),
    "company": ("company", "company name", "firm", "firm name", "organisation", "organization", "business",
                "business name", "brand"),
    "email": ("email", "e mail", "email id", "email address", "mail", "mail id"),
    "phone": ("phone", "phone no", "phone number", "mobile", "mobile no", "mobile number", "contact no",
              "contact number", "whatsapp", "whatsapp no", "whatsapp number", "tel", "telephone", "cell"),
    "country": ("country",),
    "buyer_type": ("buyer type", "type", "customer type", "business type", "buyer"),
    "category": ("category", "interested in", "product", "products", "product category"),
    "quantity": ("quantity", "qty", "volume", "order quantity", "moq"),
    "message": ("message", "requirement", "requirements", "what they need", "need", "needs", "notes", "note",
                "remarks", "remark", "comments", "comment", "details"),
}
FIELD_OF = {alias: field for field, names in ALIASES.items() for alias in names}
# Same choices as the form's "Buyer type" list (internal-leads/page.tsx)
BUYER_TYPES = ("Distributor", "Retailer", "Importer", "Brand (private label)", "Other")
FIELDS = ("name", "company", "email", "phone", "country", "buyer_type", "category_slug", "quantity", "message")


def _max_len(field: str) -> int:
    """The form's own limit for a field, read from InternalLeadIn so both always agree."""
    for rule in InternalLeadIn.model_fields[field].metadata:
        if getattr(rule, "max_length", None):
            return rule.max_length
    return MAX_CELL


def _norm(header: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", header.lower()).split())


def _text(value) -> str:
    """A cell as text. Excel keeps a phone typed as a number as 9876543210.0: shown without the ".0"."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()[:10]
    return str(value).strip()


def _table(filename: str, data: bytes) -> list[list[str]]:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "xls":
        raise AppError(422, "file_type", "Old Excel files (.xls) can't be read. In Excel, use Save As > .xlsx.")
    if ext not in ("xlsx", "csv"):
        raise AppError(422, "file_type", "Please choose an Excel (.xlsx) or CSV file.")
    if len(data) > MAX_BYTES:
        raise AppError(413, "too_big", "Max 10 MB for a file to read.")
    if not data or not file_check.is_valid(ext, data):
        raise AppError(422, "file_broken", f"This file looks damaged, or isn't really a .{ext} file.")
    if ext == "xlsx":
        try:
            ws = load_workbook(io.BytesIO(data), read_only=True, data_only=True).active  # values, never formulas
            rows = [[_text(c) for c in row]
                    for row in ws.iter_rows(max_row=MAX_ROWS * 2 + 1, max_col=MAX_COLS, values_only=True)]
        except Exception as e:  # noqa: BLE001 - openpyxl raises many kinds of error for a bad file
            raise AppError(422, "bad_file", "Could not read this Excel file.") from e
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1252", errors="replace")  # Excel's "CSV" on Windows
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")  # some Excel setups use ";"
        except csv.Error:
            dialect = csv.excel
        try:
            reader = csv.reader(io.StringIO(text), dialect)
            rows = [[c.strip() for c in row[:MAX_COLS]] for _, row in zip(range(MAX_ROWS * 2 + 1), reader)]
        except csv.Error as e:
            raise AppError(422, "bad_file", "Could not read this CSV file.") from e
    return [r for r in rows if any(r)]  # Excel files often carry empty formatted rows


def _category(text: str, categories: dict[str, str]) -> str:
    return categories.get(text.lower(), "") or categories.get(_norm(text), "")


def _buyer_type(text: str) -> str:
    t = text.lower()
    return next((b for b in BUYER_TYPES if b.lower() == t or b.lower().startswith(t[:5]) and len(t) >= 5), "")


def _lead(pairs: list[tuple[str, str]], categories: dict[str, str]) -> dict:
    """[(column name, value), ...] -> {"fields": the form's fields ("" = not in the file), "extra": the rest}."""
    fields = dict.fromkeys(FIELDS, "")
    extra: dict[str, str] = {}
    for header, value in pairs:
        if not value:
            continue
        field = FIELD_OF.get(_norm(header))
        if field == "category" and (slug := _category(value, categories)):
            fields["category_slug"] = fields["category_slug"] or slug
        elif field == "buyer_type" and (kind := _buyer_type(value)):
            fields["buyer_type"] = fields["buyer_type"] or kind
        elif field and field not in ("category", "buyer_type") and not fields[field]:
            one_line = field != "message"
            fields[field] = (" ".join(value.split()) if one_line else value)[:_max_len(field)]
        else:  # no field for it, a value we couldn't match (an unknown category) or a second phone column
            extra[header[:100] or "(no name)"] = value[:MAX_CELL]
    return {"fields": fields, "extra": extra}


def read(filename: str, data: bytes, categories: dict[str, str]) -> dict:
    """The file's leads, ready for the form. `categories`: name or slug (lower case) -> slug."""
    table = _table(filename, data)
    if not table:
        raise AppError(422, "empty", "This file has no data.")
    # Columns really used (Excel pads every row with empty cells up to MAX_COLS)
    width = max(max(i for i, c in enumerate(r) if c) + 1 for r in table)
    known_across = sum(_norm(h) in FIELD_OF for h in table[0])
    known_down = sum(bool(r) and _norm(r[0]) in FIELD_OF for r in table)
    if width <= 3 and known_down >= 2 and known_down > known_across:  # a card: "Field | Value" per row
        leads = [_lead([(r[0], " ".join(c for c in r[1:] if c)) for r in table], categories)]
        more = False
    else:  # a table: headers on top, one lead per row
        headers = table[0]
        body = table[1:]
        if not body:
            raise AppError(422, "empty", "This file has column names but no rows under them.")
        more = len(body) > MAX_ROWS
        leads = [_lead(list(zip(headers, r)), categories) for r in body[:MAX_ROWS]]
    return {"leads": leads, "more_rows": more}
