"""ReviewGuard: product context around an explainable ML model."""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal
import logging
import os
import re

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend import database as db
from backend.intelligence import analyze_review, get_model_info
from backend.security import hash_password, verify_password, new_token, token_digest

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST = PROJECT_ROOT / "frontend" / "dist"
STATIC_ASSETS = DIST / "assets"
bearer = HTTPBearer(auto_error=False)


def demo_enabled():
    return os.getenv("SEED_DEMO", "true").lower() in {"1", "true", "yes"}


@asynccontextmanager
async def lifespan(app):
    db.create_tables()
    from backend.provision import provision_admin
    provision_admin()
    if os.getenv("SEED_CATALOGUE", "false").lower() in {"1", "true", "yes"}:
        from backend.seed import seed_catalogue
        seed_catalogue()
    if demo_enabled():
        db.seed_demo(analyze_review, hash_password)
    yield


app = FastAPI(title="ReviewGuard - Product Review Intelligence", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000").split(",") if x.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
api = APIRouter()


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(InputModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class RegisterRequest(LoginRequest):
    name: str = Field(min_length=2, max_length=80)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must contain at least two characters")
        return value


class ReviewRequest(InputModel):
    review: str = Field(min_length=10, max_length=5000)

    @field_validator("review")
    @classmethod
    def valid_review(cls, value):
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Write at least 10 characters")
        return value


class ProductReviewRequest(ReviewRequest):
    rating: int = Field(ge=1, le=5, strict=True)


class OrderRequest(InputModel):
    product_id: int = Field(gt=0, strict=True)
    quantity: int = Field(default=1, ge=1, le=10, strict=True)


class ModerationRequest(InputModel):
    status: Literal["verified", "removed", "active"]


def public_user(user):
    return {key: user[key] for key in ("id", "name", "email", "role")}


def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Sign in to continue", headers={"WWW-Authenticate": "Bearer"})
    user = db.get_session_user(token_digest(credentials.credentials))
    if not user:
        raise HTTPException(401, "Your session has expired. Please sign in again.", headers={"WWW-Authenticate": "Bearer"})
    return user


User = Annotated[dict, Depends(current_user)]


def admin_user(user: User):
    if user["role"] != "admin":
        raise HTTPException(403, "Administrator access is required")
    return user


Admin = Annotated[dict, Depends(admin_user)]


def start_session(user):
    token = new_token()
    expiry = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    db.create_session(user["id"], token_digest(token), expiry)
    return {"token": token, "token_type": "bearer", "expires_at": expiry, "user": public_user(user)}


def require_product(product_id):
    product = db.get_product(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    return product


def run_analysis(review, context=None):
    try:
        return analyze_review(review, context=context)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except (FileNotFoundError, RuntimeError) as exc:
        logger.exception("Model inference unavailable")
        raise HTTPException(503, "The ML model is unavailable. Check model files and backend logs.") from exc


@api.get("/health", tags=["System"])
def health():
    return {"status": "ok", "version": "2.0.0", "demo_mode": demo_enabled(), "database": os.getenv("DB_ENGINE", "sqlite")}


@api.get("/model-info", tags=["Intelligence"])
def model_info():
    try:
        return {**get_model_info(), "demo_mode": demo_enabled()}
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(503, "Model artifacts are unavailable") from exc


@api.post("/auth/register", status_code=201, tags=["Accounts"])
def register(request: RegisterRequest):
    if db.get_user_by_email(request.email):
        raise HTTPException(409, "An account with this email already exists")
    try:
        user = db.create_user(request.name, request.email, hash_password(request.password))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return start_session(user)


@api.post("/auth/login", tags=["Accounts"])
def login(request: LoginRequest):
    user = db.get_user_by_email(request.email)
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    return start_session(user)


@api.get("/auth/me", tags=["Accounts"])
def me(user: User):
    return public_user(user)


@api.post("/auth/logout", tags=["Accounts"])
def logout(user: User, credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]):
    db.delete_session(token_digest(credentials.credentials))
    return {"message": "Signed out"}


@api.get("/products", tags=["Products"])
def products(search: str = Query("", max_length=120), category: str = Query("", max_length=80)):
    return db.list_products(search=search, category=category)


@api.get("/products/{product_id}", tags=["Products"])
def product(product_id: int):
    return require_product(product_id)


@api.get("/products/{product_id}/reviews", tags=["Reviews"])
def product_reviews(product_id: int):
    require_product(product_id)
    return db.list_product_reviews(product_id)


@api.get("/products/{product_id}/analytics", tags=["Analytics"])
def analytics(product_id: int):
    require_product(product_id)
    return db.get_product_analytics(product_id)


@api.post("/products/{product_id}/reviews", status_code=201, tags=["Reviews"])
def submit_review(product_id: int, request: ProductReviewRequest, user: User):
    product = require_product(product_id)
    context = db.user_review_context(user["id"], request.review)
    context.update(verified_purchase=db.has_purchase(user["id"], product_id), product=product)
    analysis = run_analysis(request.review, context=context)
    try:
        return db.create_product_review(user["id"], product_id, request.rating, request.review, analysis)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@api.get("/me/reviews", tags=["Accounts"])
def my_reviews(user: User):
    return db.get_user_reviews(user["id"])


@api.post("/orders", status_code=201, tags=["Demo purchases"])
def purchase(request: OrderRequest, user: User):
    require_product(request.product_id)
    return db.create_order(user["id"], request.product_id, request.quantity)


@api.get("/orders", tags=["Demo purchases"])
def orders(user: User):
    return db.get_orders(user["id"])


@api.post("/predict", tags=["Intelligence"])
def predict_review(request: ReviewRequest):
    analysis = run_analysis(request.review)
    db.save_review(**{key: analysis[key] for key in ("review", "prediction", "confidence", "fake_probability", "genuine_probability")})
    return analysis


@api.get("/history", tags=["Intelligence"])
def history():
    return db.get_review_history(limit=20)


@api.get("/stats", tags=["Intelligence"])
def stats():
    return db.get_dashboard_stats()


@api.get("/admin/stats", tags=["Administration"])
def admin_stats(user: Admin):
    return db.get_admin_stats()


@api.get("/admin/reviews", tags=["Administration"])
def admin_reviews(user: Admin, status: Literal["all", "suspicious", "verified", "removed", "active"] = "all"):
    return db.list_admin_reviews(status=status)


@api.patch("/admin/reviews/{review_id}", tags=["Administration"])
def moderate(review_id: int, request: ModerationRequest, user: Admin):
    if not db.get_product_review(review_id):
        raise HTTPException(404, "Review not found")
    return db.moderate_review(review_id, request.status, user["id"])


app.include_router(api, prefix="/api")
app.include_router(api, include_in_schema=False)

# Keep this mount available even if the API is started before `npm run build`.
# Vite writes fingerprinted JS/CSS files into this folder later, and a browser
# refresh can then load them without requiring another backend restart.
STATIC_ASSETS.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=STATIC_ASSETS), name="assets")


@app.get("/", include_in_schema=False)
def home():
    if (DIST / "index.html").exists():
        return FileResponse(DIST / "index.html")
    return {"message": "ReviewGuard API is running", "docs": "/docs", "frontend": "http://localhost:5173"}


@app.get("/favicon.svg", include_in_schema=False)
def favicon():
    return FileResponse(PROJECT_ROOT / "frontend" / "public" / "favicon.svg")
