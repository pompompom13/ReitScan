from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
import models, schemas, auth

router = APIRouter(prefix="/api/b2c", tags=["b2c"])


@router.get("/products", response_model=List[schemas.ProductOut])
def search_products(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(models.Product)
    if q:
        query = query.filter(
            models.Product.name.ilike(f"%{q}%") |
            models.Product.brand.ilike(f"%{q}%") |
            models.Product.category.ilike(f"%{q}%")
        )
    if category:
        query = query.filter(models.Product.category == category)
    products = query.limit(20).all()
    result = []
    for p in products:
        out = schemas.ProductOut(
            id=p.id, name=p.name, category=p.category, brand=p.brand,
            description=p.description,
            rating_wb=p.rating_wb, rating_ozon=p.rating_ozon, rating_ym=p.rating_ym,
            rating_gmaps=p.rating_gmaps, rating_2gis=p.rating_2gis, rating_zoon=p.rating_zoon,
            price_wb=p.price_wb, price_ozon=p.price_ozon, price_ym=p.price_ym,
            avg_rating=p.avg_rating, review_count=len(p.reviews),
        )
        result.append(out)
    return result


@router.get("/products/{product_id}", response_model=schemas.ProductDetail)
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Товар не найден")

    reviews_out = []
    for r in sorted(p.reviews, key=lambda x: x.created_at, reverse=True)[:30]:
        resp = None
        if r.response:
            resp = schemas.ReviewResponseOut(
                id=r.response.id,
                author_name=r.response.author_name,
                text=r.response.text,
                created_at=r.response.created_at,
            )
        reviews_out.append(schemas.ReviewOut(
            id=r.id, author_name=r.author_name, text=r.text,
            rating=r.rating, platform=r.platform, sentiment=r.sentiment,
            topics=r.topics, created_at=r.created_at,
            is_verified=r.is_verified, response=resp,
        ))

    return schemas.ProductDetail(
        id=p.id, name=p.name, category=p.category, brand=p.brand,
        description=p.description,
        rating_wb=p.rating_wb, rating_ozon=p.rating_ozon, rating_ym=p.rating_ym,
        rating_gmaps=p.rating_gmaps, rating_2gis=p.rating_2gis, rating_zoon=p.rating_zoon,
        price_wb=p.price_wb, price_ozon=p.price_ozon, price_ym=p.price_ym,
        avg_rating=p.avg_rating, review_count=len(p.reviews),
        reviews=reviews_out,
    )


@router.post("/reviews", response_model=schemas.ReviewOut)
def create_review(
    data: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    product = db.query(models.Product).filter(models.Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    # Auto-detect sentiment
    positive_words = ["отлично", "хорошо", "вкусно", "люблю", "нравится", "рекомендую",
                      "супер", "класс", "прекрасно", "замечательно", "отличный", "лучший"]
    negative_words = ["плохо", "ужасно", "не понравилось", "разочарован", "брак",
                      "возврат", "жалоба", "отстой", "никуда", "безобразие"]

    text_lower = data.text.lower()
    if data.rating >= 4 or any(w in text_lower for w in positive_words):
        sentiment = "positive"
    elif data.rating <= 2 or any(w in text_lower for w in negative_words):
        sentiment = "negative"
    else:
        sentiment = "neutral"

    # Auto-detect topics
    topic_map = {
        "качество": ["качество", "вкус", "состав", "натуральный", "свежий"],
        "упаковка": ["упаковка", "упак", "коробка", "обёртка", "пакет"],
        "цена": ["цена", "стоимость", "дорого", "дёшево", "выгодно", "скидка"],
        "доставка": ["доставка", "курьер", "доставили", "привезли", "быстро"],
        "сервис": ["сервис", "обслуживание", "персонал", "сотрудник", "помогли"],
    }
    detected_topics = []
    for topic, keywords in topic_map.items():
        if any(kw in text_lower for kw in keywords):
            detected_topics.append(topic)

    review = models.Review(
        product_id=data.product_id,
        author_id=current_user.id,
        author_name=current_user.username,
        text=data.text,
        rating=data.rating,
        platform="ratescan",
        sentiment=sentiment,
        topics=",".join(detected_topics) if detected_topics else None,
        is_verified=True,
    )
    db.add(review)

    # Award points
    points_earned = 10 + (5 if len(data.text) > 50 else 0)
    current_user.points += points_earned
    db.commit()
    db.refresh(review)

    return schemas.ReviewOut(
        id=review.id, author_name=review.author_name, text=review.text,
        rating=review.rating, platform=review.platform, sentiment=review.sentiment,
        topics=review.topics, created_at=review.created_at,
        is_verified=review.is_verified, response=None,
    )


@router.get("/my-reviews", response_model=List[schemas.ReviewOut])
def my_reviews(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    reviews = (
        db.query(models.Review)
        .filter(models.Review.author_id == current_user.id)
        .order_by(models.Review.created_at.desc())
        .all()
    )
    result = []
    for r in reviews:
        resp = None
        if r.response:
            resp = schemas.ReviewResponseOut(
                id=r.response.id, author_name=r.response.author_name,
                text=r.response.text, created_at=r.response.created_at,
            )
        result.append(schemas.ReviewOut(
            id=r.id, author_name=r.author_name, text=r.text,
            rating=r.rating, platform=r.platform, sentiment=r.sentiment,
            topics=r.topics, created_at=r.created_at,
            is_verified=r.is_verified, response=resp,
        ))
    return result


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    cats = db.query(models.Product.category).distinct().all()
    return [c[0] for c in cats]
