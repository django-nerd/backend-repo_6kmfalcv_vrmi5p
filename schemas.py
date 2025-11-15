"""
Database Schemas for the E‑Commerce App

Each Pydantic model represents a collection in MongoDB. The collection name is the
lowercase of the class name (e.g., User -> "user").
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List


class User(BaseModel):
    """
    Users collection schema
    Collection name: "user"
    """
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    password_hash: str = Field(..., description="Hashed password")
    address: Optional[str] = Field(None, description="Shipping address")
    is_active: bool = Field(True, description="Whether user is active")


class ProductImage(BaseModel):
    url: str
    alt: Optional[str] = None


class ProductVariant(BaseModel):
    size: Optional[str] = None
    color: Optional[str] = None
    stock: int = 0


class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product"
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    images: List[ProductImage] = Field(default_factory=list)
    variants: List[ProductVariant] = Field(default_factory=list)
    in_stock: bool = Field(True, description="Whether product is in stock")


class CartItem(BaseModel):
    product_id: str
    quantity: int = Field(1, ge=1)
    size: Optional[str] = None
    color: Optional[str] = None


class Cart(BaseModel):
    """
    Shopping cart collection schema
    Collection name: "cart"
    """
    user_id: str
    items: List[CartItem] = Field(default_factory=list)


class OrderItem(BaseModel):
    product_id: str
    title: str
    unit_price: float
    quantity: int
    size: Optional[str] = None
    color: Optional[str] = None


class Order(BaseModel):
    """
    Orders collection schema
    Collection name: "order"
    """
    user_id: str
    items: List[OrderItem]
    total: float
    status: str = Field("pending", description="Order status: pending, paid, shipped, delivered, cancelled")
    shipping_address: Optional[str] = None
