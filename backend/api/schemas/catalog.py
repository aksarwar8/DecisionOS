from pydantic import BaseModel, Field


class ProductCatalogEntry(BaseModel):
    product_id: int = Field(gt=0)
    item_id: str
    category: str | None
    department: str | None


class ProductCatalogPage(BaseModel):
    products: list[ProductCatalogEntry]
    total: int = Field(ge=0)
    limit: int = Field(gt=0)
    offset: int = Field(ge=0)


class StoreCatalogEntry(BaseModel):
    store_id: int = Field(gt=0)
    store_code: str
    state: str | None


class CategoryList(BaseModel):
    categories: list[str]


class DepartmentList(BaseModel):
    departments: list[str]


class StateList(BaseModel):
    states: list[str]
