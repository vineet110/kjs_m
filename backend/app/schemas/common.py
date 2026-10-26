"""Small shared validators (no extra packages)."""
import re
from typing import Annotated

from pydantic import AfterValidator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def _check_email(v: str) -> str:
    v = v.strip().lower()
    if not _EMAIL_RE.match(v) or len(v) > 255:
        raise ValueError("Please enter a valid email address.")
    return v


Email = Annotated[str, AfterValidator(_check_email)]


def _one_line(v: str) -> str:
    # Line breaks and control characters in a name end up in email subjects and logs;
    # "Bob\r\nX" once stopped every notification email. Collapse all whitespace to single spaces.
    return " ".join(v.split())


OneLine = Annotated[str, AfterValidator(_one_line)]


def _check_link(v: str) -> str:
    v = v.strip()
    # Only our own pages ("/products/x") or https:// sites. Blocks javascript: links, which would
    # run code as our website for whoever clicks (e.g. an admin clicking the offers ticker).
    if v and not (v.startswith("https://") or (v.startswith("/") and not v.startswith("//"))) or "\\" in v:
        raise ValueError("Link must start with / (a page on our site) or https://")
    return v


SafeLink = Annotated[str, AfterValidator(_check_link)]
