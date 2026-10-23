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
