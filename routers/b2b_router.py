from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from collections import defaultdict
from datetime import datetime, timedelta
from database import get_db
import models, schemas, auth

router = APIRouter(prefix="/api/b2b", tags=["b2b"])


def _review_out(r: models.Review) -> schemas.ReviewOut:
    resp = None
    if r.response:
        resp = schemas.ReviewResponseOut(
            id=r.response.id, author_name=r.response.author_name,
            text=r.response.text, created_at=r.response.created_at,
        )
    return schemas.ReviewOut(
        id=r.id, author_name=r.author_name, text=r.text,
        rating=r.rating, platform=r.platform, sentiment=r.sentiment,
        topics=r.topics, created_at=r.created_at,
        is_verified=r.is_verified, response=resp,
    )


@router.get("/dashboard", response_model=schemas.DashboardData)
def dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    profile = current_user.business
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль бизнеса не найден")

    # Gather all reviews for this business's products
    all_reviews = []
    for product in profile.products:
        all_reviews.extend(product.reviews)

    total = len(all_reviews)
    avg = round(sum(r.rating for r in all_reviews) / total, 2) if total else 0

    # Platform breakdown
    platform_counts = defaultdict(list)
    for r in all_reviews:
        platform_counts[r.platform].append(r.rating)
    platform_breakdown = {
        p: round(sum(v) / len(v), 1) for p, v in platform_counts.items()
    }

    # Topic breakdown (count mentions)
    topic_counts = defaultdict(int)
    for r in all_reviews:
        if r.topics:
            for t in r.topics.split(","):
                topic_counts[t.strip()] += 1

    topic_breakdown = dict(sorted(topic_counts.items(), key=lambda x: -x[1]))

    # Sentiment
    sentiments = defaultdict(int)
    for r in all_reviews:
        sentiments[r.sentiment] += 1

    # Monthly ratings (last 6 months)
    now = datetime.utcnow()
    monthly = []
    for i in range(5, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=30 * i)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        month_end = (month_start + timedelta(days=32)).replace(day=1)
        month_reviews = [
            r for r in all_reviews
            if month_start <= r.created_at < month_end
        ]
        avg_m = round(sum(r.rating for r in month_reviews) / len(month_reviews), 2) if month_reviews else None
        monthly.append({
            "month": month_start.strftime("%b %Y"),
            "avg_rating": avg_m,
            "count": len(month_reviews),
        })

    # Response rate
    responded = sum(1 for r in all_reviews if r.response is not None)
    response_rate = round(responded / total * 100, 1) if total else 0

    recent = sorted(all_reviews, key=lambda x: x.created_at, reverse=True)[:10]

    return schemas.DashboardData(
        brand_name=profile.brand_name,
        total_reviews=total,
        avg_rating=avg,
        platform_breakdown=platform_breakdown,
        topic_breakdown=topic_breakdown,
        sentiment_breakdown=dict(sentiments),
        monthly_ratings=monthly,
        recent_reviews=[_review_out(r) for r in recent],
        response_rate=response_rate,
    )


@router.get("/reviews")
def get_reviews(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    profile = current_user.business
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")

    result = []
    for product in profile.products:
        for r in sorted(product.reviews, key=lambda x: x.created_at, reverse=True):
            out = _review_out(r)
            result.append({**out.model_dump(), "product_name": product.name})
    return result


@router.post("/reviews/{review_id}/respond")
def respond_to_review(
    review_id: int,
    data: schemas.RespondReview,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    review = db.query(models.Review).filter(models.Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Отзыв не найден")

    # Verify the review belongs to this business
    profile = current_user.business
    product_ids = [p.id for p in profile.products]
    if review.product_id not in product_ids:
        raise HTTPException(status_code=403, detail="Нет доступа")

    if review.response:
        review.response.text = data.text
        review.response.created_at = datetime.utcnow()
    else:
        resp = models.ReviewResponse(
            review_id=review_id,
            author_name=f"Представитель {profile.brand_name}",
            text=data.text,
        )
        db.add(resp)

    db.commit()
    return {"status": "ok", "message": "Ответ сохранён"}


@router.get("/competitors")
def competitors(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    profile = current_user.business
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")

    my_products = profile.products
    if not my_products:
        return []

    category = my_products[0].category

    # Get all products in same category
    all_products = (
        db.query(models.Product)
        .filter(models.Product.category == category)
        .all()
    )

    result = []
    for p in all_products:
        reviews = p.reviews
        total = len(reviews)
        avg = round(sum(r.rating for r in reviews) / total, 1) if total else 0
        positive = sum(1 for r in reviews if r.sentiment == "positive")
        negative = sum(1 for r in reviews if r.sentiment == "negative")
        topics = defaultdict(int)
        for r in reviews:
            if r.topics:
                for t in r.topics.split(","):
                    topics[t.strip()] += 1

        result.append({
            "id": p.id,
            "name": p.name,
            "brand": p.brand,
            "is_mine": p.business_id == profile.id,
            "avg_rating": avg,
            "total_reviews": total,
            "positive_pct": round(positive / total * 100) if total else 0,
            "negative_pct": round(negative / total * 100) if total else 0,
            "rating_wb": p.rating_wb,
            "rating_ozon": p.rating_ozon,
            "rating_ym": p.rating_ym,
            "top_topics": dict(sorted(topics.items(), key=lambda x: -x[1])[:3]),
        })

    return sorted(result, key=lambda x: -x["avg_rating"])
