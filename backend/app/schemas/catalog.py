from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, model_validator


class CategoryOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    product_count: int = 0


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

    @model_validator(mode="after")
    def _no_null_for_required(self):
        empty = [f for f in self.model_fields_set if f != "offer_percent" and getattr(self, f) is None]
        if empty:
            raise ValueError(f"{', '.join(sorted(empty))} can't be empty")
        return self
