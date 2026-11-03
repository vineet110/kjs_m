from pydantic import BaseModel, Field, field_validator, model_validator


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


class ProductIn(BaseModel):
    category_slug: str
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=4000)
    pack_formats: str = Field(default="", max_length=255)
    moq: str = Field(default="", max_length=120)
    # A file in our own `public/` folder, e.g. /images/products/coffee.jpg. Next.js 16 refuses image
    # addresses with "?" and crashes the page on other websites' images, so only plain local paths.
    image_path: str = Field(default="", max_length=255, pattern=r"^(/[A-Za-z0-9_-][A-Za-z0-9._/-]*)?$")
    private_label: bool = True
    is_best_seller: bool = False
    # "Up to X% OFF" on the website; None = no offer. Whole numbers 1 to 90 (12.5 is refused, not rounded)
    offer_percent: int | None = Field(default=None, ge=1, le=90)

    @field_validator("image_path")
    @classmethod
    def _no_dot_dot(cls, v: str) -> str:
        if ".." in v or "//" in v:
            raise ValueError("must be a plain path like /images/products/coffee.jpg")
        return v


class ProductPatchIn(BaseModel):
    """An edit: only the fields sent are changed (PR #16 review). A script or an older admin tab that sends
    just the name can't blank the rest or show a hidden product again. Same rules as ProductIn per field;
    only offer_percent may be null (null removes the offer)."""

    category_slug: str | None = None
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    pack_formats: str | None = Field(default=None, max_length=255)
    moq: str | None = Field(default=None, max_length=120)
    image_path: str | None = Field(default=None, max_length=255, pattern=r"^(/[A-Za-z0-9_-][A-Za-z0-9._/-]*)?$")
    private_label: bool | None = None
    is_best_seller: bool | None = None
    offer_percent: int | None = Field(default=None, ge=1, le=90)
    is_active: bool | None = None  # false = hidden from the website

    @field_validator("image_path")
    @classmethod
    def _no_dot_dot(cls, v: str | None) -> str | None:
        return v if v is None else ProductIn._no_dot_dot(v)

    @model_validator(mode="after")
    def _no_null_for_required(self):
        empty = [f for f in self.model_fields_set if f != "offer_percent" and getattr(self, f) is None]
        if empty:
            raise ValueError(f"{', '.join(sorted(empty))} can't be empty")
        return self
