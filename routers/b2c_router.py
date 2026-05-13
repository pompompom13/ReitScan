from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from collections import defaultdict
import random, string
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
    return [_product_out(p) for p in products]


@router.get("/products/{product_id}", response_model=schemas.ProductDetail)
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Товар не найден")

    reviews_out = []
    for r in sorted(p.reviews, key=lambda x: x.created_at, reverse=True)[:30]:
        reviews_out.append(_review_out(r))

    out = _product_out(p)
    return schemas.ProductDetail(**out.model_dump(), reviews=reviews_out)


@router.get("/products/{product_id}/analysis")
def product_analysis(product_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Товар не найден")

    # Pros and cons from topic analysis
    pros_topics: dict = defaultdict(lambda: {"count": 0, "examples": []})
    cons_topics: dict = defaultdict(lambda: {"count": 0, "examples": []})
    star_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    for r in p.reviews:
        star_dist[r.rating] = star_dist.get(r.rating, 0) + 1
        if not r.topics:
            continue
        for topic in r.topics.split(","):
            topic = topic.strip()
            if r.sentiment == "positive":
                pros_topics[topic]["count"] += 1
                if len(pros_topics[topic]["examples"]) < 2:
                    pros_topics[topic]["examples"].append(r.text[:110])
            elif r.sentiment == "negative":
                cons_topics[topic]["count"] += 1
                if len(cons_topics[topic]["examples"]) < 2:
                    cons_topics[topic]["examples"].append(r.text[:110])

    total = max(len(p.reviews), 1)
    pros = [
        {"topic": t, "count": v["count"], "pct": round(v["count"] / total * 100),
         "examples": v["examples"]}
        for t, v in sorted(pros_topics.items(), key=lambda x: -x[1]["count"])
    ]
    cons = [
        {"topic": t, "count": v["count"], "pct": round(v["count"] / total * 100),
         "examples": v["examples"]}
        for t, v in sorted(cons_topics.items(), key=lambda x: -x[1]["count"])
    ]

    # Per-platform breakdown
    platform_data: dict = defaultdict(lambda: {
        "reviews": [], "pros": defaultdict(int), "cons": defaultdict(int)
    })
    for r in p.reviews:
        platform_data[r.platform]["reviews"].append(r)
        if r.topics:
            for t in r.topics.split(","):
                t = t.strip()
                if r.sentiment == "positive":
                    platform_data[r.platform]["pros"][t] += 1
                elif r.sentiment == "negative":
                    platform_data[r.platform]["cons"][t] += 1

    platform_breakdown = {}
    for plat, data in platform_data.items():
        revs = data["reviews"]
        avg = round(sum(r.rating for r in revs) / len(revs), 1) if revs else 0
        positive = sum(1 for r in revs if r.sentiment == "positive")
        top_pro = max(data["pros"].items(), key=lambda x: x[1])[0] if data["pros"] else None
        top_con = max(data["cons"].items(), key=lambda x: x[1])[0] if data["cons"] else None
        platform_breakdown[plat] = {
            "avg": avg,
            "count": len(revs),
            "positive_pct": round(positive / len(revs) * 100) if revs else 0,
            "top_pro": top_pro,
            "top_con": top_con,
        }

    # Category rank
    all_in_cat = db.query(models.Product).filter(models.Product.category == p.category).all()
    cat_sorted = sorted(all_in_cat, key=lambda x: -x.avg_rating)
    my_rank = next((i + 1 for i, x in enumerate(cat_sorted) if x.id == p.id), len(cat_sorted))

    # Radar scores (avg rating of reviews mentioning each dimension)
    dim_map = {
        "вкус_качество": ["вкус", "качество"],
        "цена": ["цена"],
        "упаковка": ["упаковка"],
        "доставка": ["доставка"],
        "сервис": ["сервис"],
    }
    radar = {}
    for dim, keywords in dim_map.items():
        matching = [r for r in p.reviews if r.topics and any(k in r.topics for k in keywords)]
        radar[dim] = round(sum(r.rating for r in matching) / len(matching), 1) if matching else 3.0

    return {
        "pros": pros,
        "cons": cons,
        "platform_breakdown": platform_breakdown,
        "star_distribution": star_dist,
        "radar": radar,
        "category_rank": {
            "position": my_rank,
            "total": len(all_in_cat),
            "category": p.category,
            "competitors": [
                {"id": x.id, "name": x.name, "avg_rating": x.avg_rating,
                 "review_count": len(x.reviews)}
                for x in cat_sorted
            ],
        },
    }


@router.post("/reviews", response_model=schemas.ReviewOut)
def create_review(
    data: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    product = db.query(models.Product).filter(models.Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    positive_words = ["отлично", "хорошо", "вкусно", "люблю", "нравится", "рекомендую",
                      "супер", "класс", "прекрасно", "замечательно", "отличный", "лучший"]
    negative_words = ["плохо", "ужасно", "не понравилось", "разочарован", "брак",
                      "возврат", "жалоба", "отстой", "никуда"]

    text_lower = data.text.lower()
    if data.rating >= 4 or any(w in text_lower for w in positive_words):
        sentiment = "positive"
    elif data.rating <= 2 or any(w in text_lower for w in negative_words):
        sentiment = "negative"
    else:
        sentiment = "neutral"

    topic_map = {
        "качество": ["качество", "состав", "натуральный", "свежий"],
        "вкус": ["вкус", "вкусный", "вкусно", "нежный", "сладко", "кисло"],
        "упаковка": ["упаковка", "упак", "коробка", "обёртка", "пакет"],
        "цена": ["цена", "стоимость", "дорого", "дёшево", "выгодно", "скидка"],
        "доставка": ["доставка", "курьер", "доставили", "привезли", "быстро"],
        "сервис": ["сервис", "обслуживание", "персонал", "сотрудник", "помогли"],
    }
    detected_topics = [
        topic for topic, keywords in topic_map.items()
        if any(kw in text_lower for kw in keywords)
    ]

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

    points_earned = 10 + (5 if len(data.text) > 50 else 0)
    current_user.points += points_earned
    db.commit()
    db.refresh(review)

    return _review_out(review)


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
    return [_review_out(r) for r in reviews]


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    cats = db.query(models.Product.category).distinct().all()
    return [c[0] for c in cats]


@router.get("/rewards")
def list_rewards(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    rewards = db.query(models.Reward).filter(models.Reward.is_active == True).all()
    purchased_ids = {ur.reward_id for ur in current_user.purchased_rewards}
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "partner": r.partner,
            "points_cost": r.points_cost,
            "category": r.category,
            "icon": r.icon,
            "badge_color": r.badge_color,
            "already_purchased": r.id in purchased_ids,
            "can_afford": current_user.points >= r.points_cost,
        }
        for r in rewards
    ]


@router.post("/rewards/{reward_id}/purchase")
def purchase_reward(
    reward_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    reward = db.query(models.Reward).filter(models.Reward.id == reward_id).first()
    if not reward or not reward.is_active:
        raise HTTPException(status_code=404, detail="Награда не найдена")
    if current_user.points < reward.points_cost:
        raise HTTPException(status_code=400, detail="Недостаточно баллов")

    already = db.query(models.UserReward).filter(
        models.UserReward.user_id == current_user.id,
        models.UserReward.reward_id == reward_id,
    ).first()
    if already:
        raise HTTPException(status_code=400, detail="Уже куплено")

    promo_code = "RS-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    user_reward = models.UserReward(
        user_id=current_user.id,
        reward_id=reward_id,
        promo_code=promo_code,
    )
    db.add(user_reward)
    current_user.points -= reward.points_cost
    db.commit()

    return {
        "status": "ok",
        "promo_code": promo_code,
        "remaining_points": current_user.points,
        "message": f"Поздравляем! Ваш промокод: {promo_code}",
    }


@router.get("/my-rewards")
def my_rewards(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    user_rewards = (
        db.query(models.UserReward)
        .filter(models.UserReward.user_id == current_user.id)
        .order_by(models.UserReward.purchased_at.desc())
        .all()
    )
    return [
        {
            "id": ur.id,
            "reward_name": ur.reward.name,
            "partner": ur.reward.partner,
            "icon": ur.reward.icon,
            "promo_code": ur.promo_code,
            "purchased_at": ur.purchased_at.isoformat(),
            "is_used": ur.is_used,
        }
        for ur in user_rewards
    ]


def _product_out(p: models.Product) -> schemas.ProductOut:
    return schemas.ProductOut(
        id=p.id, name=p.name, category=p.category, brand=p.brand,
        description=p.description, business_id=p.business_id,
        rating_wb=p.rating_wb, rating_ozon=p.rating_ozon, rating_ym=p.rating_ym,
        rating_gmaps=p.rating_gmaps, rating_2gis=p.rating_2gis, rating_zoon=p.rating_zoon,
        price_wb=p.price_wb, price_ozon=p.price_ozon, price_ym=p.price_ym,
        avg_rating=p.avg_rating, review_count=len(p.reviews),
    )


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
