from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String)
    hashed_password = Column(String)
    user_type = Column(String)  # "b2c" or "b2b"
    points = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    company_name = Column(String, nullable=True)
    company_category = Column(String, nullable=True)

    reviews = relationship("Review", back_populates="author")
    business = relationship("BusinessProfile", back_populates="owner", uselist=False)


class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    brand_name = Column(String)
    category = Column(String)
    description = Column(Text, nullable=True)

    owner = relationship("User", back_populates="business")
    products = relationship("Product", back_populates="business")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String)
    brand = Column(String)
    business_id = Column(Integer, ForeignKey("business_profiles.id"), nullable=True)
    description = Column(Text, nullable=True)

    # Platform ratings
    rating_wb = Column(Float, default=0)
    rating_ozon = Column(Float, default=0)
    rating_ym = Column(Float, default=0)
    rating_gmaps = Column(Float, default=0)
    rating_2gis = Column(Float, default=0)
    rating_zoon = Column(Float, default=0)

    # Prices
    price_wb = Column(Integer, nullable=True)
    price_ozon = Column(Integer, nullable=True)
    price_ym = Column(Integer, nullable=True)

    reviews = relationship("Review", back_populates="product")
    business = relationship("BusinessProfile", back_populates="products")

    @property
    def avg_rating(self):
        ratings = [r for r in [
            self.rating_wb, self.rating_ozon, self.rating_ym,
            self.rating_gmaps, self.rating_2gis, self.rating_zoon
        ] if r > 0]
        return round(sum(ratings) / len(ratings), 1) if ratings else 0

    @property
    def review_count(self):
        return len(self.reviews)


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    author_name = Column(String)
    text = Column(Text)
    rating = Column(Integer)
    platform = Column(String, default="ratescan")  # ratescan, wb, ozon, ym, gmaps, 2gis, zoon
    topics = Column(String, nullable=True)          # comma-separated topics
    sentiment = Column(String, default="neutral")   # positive, negative, neutral
    created_at = Column(DateTime, default=datetime.utcnow)
    is_verified = Column(Boolean, default=False)

    product = relationship("Product", back_populates="reviews")
    author = relationship("User", back_populates="reviews")
    response = relationship("ReviewResponse", back_populates="review", uselist=False)


class ReviewResponse(Base):
    __tablename__ = "review_responses"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(Integer, ForeignKey("reviews.id"))
    author_name = Column(String, default="Представитель бренда")
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    review = relationship("Review", back_populates="response")
