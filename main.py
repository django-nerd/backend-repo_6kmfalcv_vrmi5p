import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId
from passlib.context import CryptContext

from database import db, create_document, get_documents
from schemas import User, Product, Cart, Order, CartItem

app = FastAPI(title="E‑Commerce Clothing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Helpers

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


# Auth models
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    token: str


# Simple token mechanism (demo)
# In a real app, use JWT. Here we create a basic token for session-like auth.

def create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc).timestamp()
    return f"tok_{user_id}_{int(now)}"


@app.get("/")
def read_root():
    return {"message": "E‑Commerce API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# Auth endpoints
@app.post("/auth/signup", response_model=AuthResponse)
def signup(payload: SignupRequest):
    existing = db["user"].find_one({"email": payload.email}) if db else None
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_doc = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    uid = create_document("user", user_doc)
    token = create_token(uid)
    return AuthResponse(user_id=uid, name=user_doc.name, email=user_doc.email, token=token)


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    user = db["user"].find_one({"email": payload.email}) if db else None
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(str(user.get("_id")))
    return AuthResponse(user_id=str(user.get("_id")), name=user.get("name"), email=user.get("email"), token=token)


# Products
@app.get("/products", response_model=List[Product])
def list_products():
    docs = get_documents("product", limit=100)
    # Convert _id to str and validate with Product model
    normalized = []
    for d in docs:
        d.pop("_id", None)
        normalized.append(Product(**d))
    return normalized


class CreateProductRequest(Product):
    pass


@app.post("/products")
def create_product(payload: CreateProductRequest):
    pid = create_document("product", payload)
    return {"product_id": pid}


# Cart
@app.get("/cart/{user_id}")
def get_cart(user_id: str):
    cart = db["cart"].find_one({"user_id": user_id}) if db else None
    if not cart:
        cart_doc = Cart(user_id=user_id, items=[])
        cid = create_document("cart", cart_doc)
        return {"cart_id": cid, "items": []}
    # sanitize
    for it in cart.get("items", []):
        it.pop("_id", None)
    return {"cart_id": str(cart.get("_id")), "items": cart.get("items", [])}


class AddToCartRequest(BaseModel):
    product_id: str
    quantity: int = 1
    size: Optional[str] = None
    color: Optional[str] = None


@app.post("/cart/{user_id}/add")
def add_to_cart(user_id: str, payload: AddToCartRequest):
    cart = db["cart"].find_one({"user_id": user_id})
    item = payload.model_dump()
    if not cart:
        cart_doc = Cart(user_id=user_id, items=[CartItem(**item)])
        cid = create_document("cart", cart_doc)
        return {"cart_id": cid, "items": [item]}
    items = cart.get("items", [])
    items.append(item)
    db["cart"].update_one({"_id": cart["_id"]}, {"$set": {"items": items, "updated_at": datetime.now(timezone.utc)}})
    return {"cart_id": str(cart["_id"]), "items": items}


# Orders (mock checkout)
class CheckoutRequest(BaseModel):
    user_id: str
    shipping_address: Optional[str] = None


@app.post("/checkout")
def checkout(payload: CheckoutRequest):
    cart = db["cart"].find_one({"user_id": payload.user_id})
    if not cart or not cart.get("items"):
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Build order items from product refs (simplified)
    order_items = []
    total = 0.0
    for it in cart.get("items", []):
        prod = db["product"].find_one({"_id": ObjectId(it["product_id"])}) if ObjectId.is_valid(it["product_id"]) else None
        title = prod.get("title") if prod else "Item"
        price = float(prod.get("price", 0)) if prod else 0.0
        qty = int(it.get("quantity", 1))
        total += price * qty
        order_items.append({
            "product_id": it["product_id"],
            "title": title,
            "unit_price": price,
            "quantity": qty,
            "size": it.get("size"),
            "color": it.get("color"),
        })

    order_doc = {
        "user_id": payload.user_id,
        "items": order_items,
        "total": round(total, 2),
        "status": "paid",
        "shipping_address": payload.shipping_address,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    oid = db["order"].insert_one(order_doc).inserted_id

    # clear cart
    db["cart"].update_one({"user_id": payload.user_id}, {"$set": {"items": [], "updated_at": datetime.now(timezone.utc)}})

    return {"order_id": str(oid), "total": order_doc["total"], "status": "paid"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
