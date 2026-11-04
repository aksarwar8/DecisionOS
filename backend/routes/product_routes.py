
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Product

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


@router.post("/")
def create_product(
    item_id: str,
    category: str,
    department: str,
    db: Session = Depends(get_db)
):
    existing_product = db.query(Product).filter(
        Product.item_id == item_id
    ).first()

    if existing_product:
        raise HTTPException(
            status_code=400,
            detail="Product already exists"
        )

    product = Product(
        item_id=item_id,
        category=category,
        department=department
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return {
        "message": "Product created successfully",
        "product_id": product.id,
        "item_id": product.item_id
    }


@router.get("/")
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).all()
