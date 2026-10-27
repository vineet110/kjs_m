from pydantic import BaseModel, Field, field_validator


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

    @field_validator("image_path")
    @classmethod
    def _no_dot_dot(cls, v: str) -> str:
        if ".." in v or "//" in v:
            raise ValueError("must be a plain path like /images/products/coffee.jpg")
        return v
