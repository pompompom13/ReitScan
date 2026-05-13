from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    username: str
    user_type: str  # "b2c" or "b2b"
    company_name: Optional[str] = None
    company_category: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user_type: str
    username: str


class UserOut(BaseModel):
    id: int
    email: str
    username: str
    user_type: str
    points: int
    company_name: Optional[str] = None
    company_category: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewResponseOut(BaseModel):
    id: int
    author_name: str
    text: str
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewOut(BaseModel):
    id: int
    author_name: str
    text: str
    rating: int
    platform: str
    sentiment: str
    topics: Optional[str] = None
    created_at: datetime
    is_verified: bool
    response: Optional[ReviewResponseOut] = None

    class Config:
        from_attributes = True


class ProductOut(BaseModel):
    id: int
    name: str
    category: str
    brand: str
    description: Optional[str] = None
    business_id: Optional[int] = None
    rating_wb: float
    rating_ozon: float
    rating_ym: float
    rating_gmaps: float
    rating_2gis: float
    rating_zoon: float
    price_wb: Optional[int] = None
    price_ozon: Optional[int] = None
    price_ym: Optional[int] = None
    avg_rating: float
    review_count: int

    class Config:
        from_attributes = True


class ProductDetail(ProductOut):
    reviews: List[ReviewOut] = []


class ReviewCreate(BaseModel):
    product_id: int
    rating: int
    text: str


class RespondReview(BaseModel):
    text: str


class DashboardData(BaseModel):
    brand_name: str
    total_reviews: int
    avg_rating: float
    platform_breakdown: dict
    topic_breakdown: dict
    sentiment_breakdown: dict
    monthly_ratings: List[dict]
    recent_reviews: List[ReviewOut]
    response_rate: float
