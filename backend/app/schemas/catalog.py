import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, field_validator, model_validator


COUNT_MAX = 100000  # most pieces per box / boxes per case (a sanity limit, not a business number)


class ProductItem(BaseModel):
    """One catalogue item of a product (R19): item number, optional variant, pack weight, pieces per box,
    boxes per case. Checked here, so a mistake is refused with a message, never silently dropped."""
    no: str = Field(min_length=1, max_length=20, pattern=r"^\S+$")  # "801", "B-12": no spaces
    variant: str = Field(default="", max_length=60)
    weight: str = Field(min_length=1, max_length=30)  # "25 g", "1 kg"
    pieces: int = Field(ge=1, le=COUNT_MAX)  # pieces per box
    per_case: int = Field(ge=1, le=COUNT_MAX)  # boxes per case

    @field_validator("no", "variant", "weight")
    @classmethod
    def no_separators(cls, v: str) -> str:
        # Admin > Products writes each item as one line, "801 | Hazelnut | 25 g | 24 | 6": a "|", a line break
        # or a tab inside a value would split it, and that product could never be saved in Admin again
        if any(ch in v for ch in "|\r\n\t"):
            raise ValueError('may not contain "|", a line break or a tab')
        return v


def _unique_numbers(items: list[ProductItem]) -> list[ProductItem]:
    numbers = [i.no for i in items]
    if len(numbers) != len(set(numbers)):
        raise ValueError("each item number may appear only once")
    return items


Items = Annotated[list[ProductItem], Field(max_length=100), AfterValidator(_unique_numbers)]


def _whole(v) -> int:
    """A count as stored: 24, 24.0 and "24" are all 24 (as before). Real junk (None, "x", 2.5, True, "²") and
    anything outside what a save allows (1 to COUNT_MAX) is 0."""
    n = 0
    if isinstance(v, int) and not isinstance(v, bool):
        n = v
    elif isinstance(v, float) and v.is_integer():
        n = int(v)
    # only 0-9: str.isdigit() also says yes to "²" or "٣", which int() can't read
    elif isinstance(v, str) and re.fullmatch(r"[0-9]{1,9}", v.strip()):
        n = int(v.strip())
    return n if 1 <= n <= COUNT_MAX else 0


def _stored_items(v) -> list[dict]:
    """Stored items made safe to show: anything that isn't an item, or has no item number, is skipped; a
    missing or odd value gets a default. One bad row (a hand edit, an old migration) never breaks the list.
    (Known: a count shown as 0 makes Admin ask for that line to be fixed before the next save; Admin names
    the line, so it is found at once. Only a hand edit of the database can cause it.)"""
    out = []
    for m in v if isinstance(v, list) else []:
        if not isinstance(m, dict) or m.get("no") is None or not str(m["no"]).strip():
            continue
        out.append({"no": str(m["no"]), "variant": str(m.get("variant") or ""), "weight": str(m.get("weight") or ""),
                    "pieces": _whole(m.get("pieces")), "per_case": _whole(m.get("per_case"))})
    return out


class ProductItemOut(BaseModel):
    """An item as stored (answers): not checked again, so one odd stored item can never break a product list
    (made safe by _stored_items first)."""
    no: str
    variant: str = ""
    weight: str = ""
    pieces: int = 0
    per_case: int = 0


class CategoryOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    product_count: int = 0


class AdminCategoryOut(BaseModel):
    """Admin > Products > Categories: every category with its Show/Hide switch."""
    id: int
    slug: str
    name: str
    is_active: bool  # its own switch
    visible: bool  # on the public site: its switch is on and its parent's (if any) too
    parent: str | None = None  # slug of the category it sits inside (SUBCATEGORIES)
    product_count: int = 0  # its own products, shown or hidden


class CategoryPatchIn(BaseModel):
    """The Show/Hide switch: only is_active. Anything else sent (name, slug) is ignored."""
    is_active: bool


class ProductOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    pack_formats: str
    moq: str
    image_path: str
    private_label: bool
    is_best_seller: bool
    offer_percent: int | None = None
    category_slug: str
    category_name: str
    is_active: bool = True
    items: Annotated[list[ProductItemOut], BeforeValidator(_stored_items)] = []
    photo_url: str | None = None  # first photo uploaded with "Show on website"; cards use it without an image_path


def _no_dot_dot(v: str) -> str:
    if ".." in v or "//" in v:
        raise ValueError("must be a plain path like /images/products/coffee.jpg")
    return v


# The rules for each product field, written once and used by both "add" (ProductIn) and "edit"
# (ProductPatchIn), so the two can't drift apart. The name is trimmed BEFORE its length is checked.
ProductName = Annotated[str, BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v),
                        Field(min_length=2, max_length=200)]
Description = Annotated[str, Field(max_length=4000)]
PackFormats = Annotated[str, Field(max_length=255)]
Moq = Annotated[str, Field(max_length=120)]
# A file in our own `public/` folder, e.g. /images/products/coffee.jpg. Next.js 16 refuses image
# addresses with "?" and crashes the page on other websites' images, so only plain local paths.
ImagePath = Annotated[str, Field(max_length=255, pattern=r"^(/[A-Za-z0-9_-][A-Za-z0-9._/-]*)?$"),
                      AfterValidator(_no_dot_dot)]
# "Up to X% OFF" on the website; None = no offer. Whole numbers 1 to 90 (12.5 is refused, not rounded)
OfferPercent = Annotated[int, Field(ge=1, le=90)]


class ProductIn(BaseModel):
    category_slug: str
    name: ProductName
    description: Description = ""
    pack_formats: PackFormats = ""
    moq: Moq = ""
    image_path: ImagePath = ""
    private_label: bool = True
    is_best_seller: bool = False
    offer_percent: OfferPercent | None = None
    items: Items = []


class ProductPatchIn(BaseModel):
    """An edit: only the fields sent are changed (PR #16 review). A script or an older admin tab that sends
    just the name can't blank the rest or show a hidden product again. Same rules as ProductIn per field;
    only offer_percent may be null (null removes the offer)."""

    category_slug: str | None = None
    name: ProductName | None = None
    description: Description | None = None
    pack_formats: PackFormats | None = None
    moq: Moq | None = None
    image_path: ImagePath | None = None
    private_label: bool | None = None
    is_best_seller: bool | None = None
    offer_percent: OfferPercent | None = None
    is_active: bool | None = None  # false = hidden from the website
    items: Items | None = None

    @model_validator(mode="after")
    def _no_null_for_required(self):
        empty = [f for f in self.model_fields_set if f != "offer_percent" and getattr(self, f) is None]
        if empty:
            raise ValueError(f"{', '.join(sorted(empty))} can't be empty")
        return self
