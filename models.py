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
    user_type = Column(String)
    points = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    company_name = Column(String, nullable=True)
    company_category = Column(String, nullable=True)
    last_daily_spin = Column(DateTime, nullable=True)

    reviews = relationship("Review", back_populates="author")
    business = relationship("BusinessProfile", back_populates="owner", uselist=False)
    purchased_rewards = relationship("UserReward", back_populates="user")
    survey_completions = relationship("SurveyCompletion", back_populates="user")
    conversations_as_b2c = relationship("Conversation", foreign_keys="Conversation.b2c_user_id", back_populates="b2c_user")


class BusinessProfile(Base):
    __tablename__ = "business_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    brand_name = Column(String)
    category = Column(String)
    description = Column(Text, nullable=True)

    owner = relationship("User", back_populates="business")
    products = relationship("Product", back_populates="business")
    surveys = relationship("Survey", back_populates="business")
    conversations = relationship("Conversation", back_populates="business")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String)
    brand = Column(String)
    business_id = Column(Integer, ForeignKey("business_profiles.id"), nullable=True)
    description = Column(Text, nullable=True)

    rating_wb = Column(Float, default=0)
    rating_ozon = Column(Float, default=0)
    rating_ym = Column(Float, default=0)
    rating_gmaps = Column(Float, default=0)
    rating_2gis = Column(Float, default=0)
    rating_zoon = Column(Float, default=0)

    price_wb = Column(Integer, nullable=True)
    price_ozon = Column(Integer, nullable=True)
    price_ym = Column(Integer, nullable=True)

    reviews = relationship("Review", back_populates="product")
    business = relationship("BusinessProfile", back_populates="products")

    @property
    def avg_rating(self):
        ratings = [r for r in [self.rating_wb, self.rating_ozon, self.rating_ym,
                                self.rating_gmaps, self.rating_2gis, self.rating_zoon] if r > 0]
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
    platform = Column(String, default="ratescan")
    topics = Column(String, nullable=True)
    sentiment = Column(String, default="neutral")
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


class Reward(Base):
    __tablename__ = "rewards"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(Text)
    partner = Column(String)
    points_cost = Column(Integer)
    category = Column(String)
    icon = Column(String, default="🎁")
    badge_color = Column(String, default="bg-indigo-100 text-indigo-700")
    is_active = Column(Boolean, default=True)
    stock = Column(Integer, default=100)

    purchases = relationship("UserReward", back_populates="reward")


class UserReward(Base):
    __tablename__ = "user_rewards"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    reward_id = Column(Integer, ForeignKey("rewards.id"))
    purchased_at = Column(DateTime, default=datetime.utcnow)
    promo_code = Column(String)
    is_used = Column(Boolean, default=False)

    user = relationship("User", back_populates="purchased_rewards")
    reward = relationship("Reward", back_populates="purchases")


# ===== SURVEYS =====

class Survey(Base):
    __tablename__ = "surveys"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(Text)
    business_id = Column(Integer, ForeignKey("business_profiles.id"))
    category = Column(String)
    target_audience = Column(Text, nullable=True)  # JSON list of product categories
    points_reward = Column(Integer, default=25)
    is_active = Column(Boolean, default=True)
    estimated_minutes = Column(Integer, default=3)
    gradient = Column(String, default="from-indigo-500 to-purple-600")
    created_at = Column(DateTime, default=datetime.utcnow)

    business = relationship("BusinessProfile", back_populates="surveys")
    questions = relationship("SurveyQuestion", back_populates="survey", order_by="SurveyQuestion.order")
    completions = relationship("SurveyCompletion", back_populates="survey")


class SurveyQuestion(Base):
    __tablename__ = "survey_questions"
    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"))
    order = Column(Integer)
    question_text = Column(Text)
    question_type = Column(String)  # "choice", "rating", "text"
    options = Column(Text, nullable=True)  # JSON string for choices

    survey = relationship("Survey", back_populates="questions")


class SurveyCompletion(Base):
    __tablename__ = "survey_completions"
    id = Column(Integer, primary_key=True, index=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    completed_at = Column(DateTime, default=datetime.utcnow)
    points_earned = Column(Integer)

    survey = relationship("Survey", back_populates="completions")
    user = relationship("User", back_populates="survey_completions")


# ===== MESSAGING =====

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    b2c_user_id = Column(Integer, ForeignKey("users.id"))
    business_id = Column(Integer, ForeignKey("business_profiles.id"))
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    subject = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_message_at = Column(DateTime, default=datetime.utcnow)
    is_read_b2b = Column(Boolean, default=False)
    is_read_b2c = Column(Boolean, default=True)

    b2c_user = relationship("User", foreign_keys=[b2c_user_id], back_populates="conversations_as_b2c")
    business = relationship("BusinessProfile", back_populates="conversations")
    product = relationship("Product")
    messages = relationship("ConversationMessage", back_populates="conversation",
                            order_by="ConversationMessage.created_at")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    sender_type = Column(String)  # "b2c" or "b2b"
    sender_name = Column(String)
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
