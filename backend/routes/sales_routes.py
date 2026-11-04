
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date

from backend.database import get_db
from backend.models import Sale, Product, Store

router = APIRouter(
    prefix="/sales",
    tags=["Sales"]
)


@router.post("/")
def create_sale(
    product_id: int,
    store_id: int,
    sale_date: date,
    sales_quantity: float,
    db: Session = Depends(get_db)
):
    # Check whether the product exists
    product = db.query(Product).filter(
        Product.id == product_id
    ).first()

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    # Check whether the store exists
    store = db.query(Store).filter(
        Store.id == store_id
    ).first()

    if not store:
        raise HTTPException(
            status_code=404,
            detail="Store not found"
        )

    # Create a new sales record
    sale = Sale(
        product_id=product_id,
        store_id=store_id,
        date=sale_date,
        sales_quantity=sales_quantity
    )

    db.add(sale)
    db.commit()
    db.refresh(sale)

    return {
        "message": "Sale recorded successfully",
        "sale_id": sale.id
    }


@router.get("/")
def get_sales(db: Session = Depends(get_db)):
    return db.query(Sale).all()
