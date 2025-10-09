from typing import Optional
from pydantic import BaseModel


class ProductModel(BaseModel):
    product_no: str  # (10)
    product_name: Optional[str] = None  # (50)
    file_path: Optional[str] = None
