
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey
from sqlalchemy.sql import func

from backend.database import Base


# 1. Products table
class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(String, unique=True, nullable=False, index=True)
    category = Column(String, nullable=True)
    department = Column(String, nullable=True)


# 2. Stores table
class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, unique=True, nullable=False, index=True)
    state = Column(String, nullable=True)


# 3. Historical sales table
class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    date = Column(Date, nullable=False)
    sales_quantity = Column(Float, nullable=False)


# 4. Forecasts table
class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    forecast_date = Column(Date, nullable=False)
    predicted_demand = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 5. Model execution history
class ModelRun(Base):
    __tablename__ = "model_runs"

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, nullable=False)
    model_version = Column(String, nullable=True)
    mae = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)
    wape = Column(Float, nullable=True)
    executed_at = Column(DateTime(timezone=True), server_default=func.now())
