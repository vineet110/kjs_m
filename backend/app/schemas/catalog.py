from pydantic import BaseModel, Field


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
    image_path: str = Field(default="", max_length=255)
    private_label: bool = True
    is_best_seller: bool = False
