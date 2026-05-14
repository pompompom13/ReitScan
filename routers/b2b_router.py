import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from collections import defaultdict
from datetime import datetime, timedelta
from io import BytesIO
from typing import List, Optional
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


def _get_all_reviews(profile: models.BusinessProfile):
    reviews = []
    for p in profile.products:
        reviews.extend(p.reviews)
    return reviews


@router.get("/dashboard", response_model=schemas.DashboardData)
def dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    profile = current_user.business
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль бизнеса не найден")

    all_reviews = _get_all_reviews(profile)
    total = len(all_reviews)
    avg = round(sum(r.rating for r in all_reviews) / total, 2) if total else 0

    platform_counts: dict = defaultdict(list)
    for r in all_reviews:
        platform_counts[r.platform].append(r.rating)
    platform_breakdown = {p: round(sum(v) / len(v), 1) for p, v in platform_counts.items()}

    topic_counts: dict = defaultdict(int)
    for r in all_reviews:
        if r.topics:
            for t in r.topics.split(","):
                topic_counts[t.strip()] += 1
    topic_breakdown = dict(sorted(topic_counts.items(), key=lambda x: -x[1]))

    sentiments: dict = defaultdict(int)
    for r in all_reviews:
        sentiments[r.sentiment] += 1

    now = datetime.utcnow()
    monthly = []
    for i in range(5, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=30 * i)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        month_end = (month_start + timedelta(days=32)).replace(day=1)
        month_reviews = [r for r in all_reviews if month_start <= r.created_at < month_end]
        avg_m = round(sum(r.rating for r in month_reviews) / len(month_reviews), 2) if month_reviews else None
        monthly.append({
            "month": month_start.strftime("%b %Y"),
            "avg_rating": avg_m,
            "count": len(month_reviews),
        })

    responded = sum(1 for r in all_reviews if r.response is not None)
    response_rate = round(responded / total * 100, 1) if total else 0

    recent = sorted(all_reviews, key=lambda x: x.created_at, reverse=True)[:10]

    product_category = profile.products[0].category if profile.products else ""
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
        product_category=product_category,
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


@router.get("/export-reviews")
def export_reviews(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    profile = current_user.business
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Отзывы"

    headers = ["Дата", "Товар/Бренд", "Площадка", "Автор", "Оценка",
               "Тональность", "Темы", "Текст отзыва", "Ответ бренда"]

    # Header styling
    header_fill = PatternFill("solid", fgColor="7C3AED")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border_side = Side(style="thin", color="D1D5DB")
    cell_border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = cell_border

    sentiment_map = {"positive": "Позитивный", "negative": "Негативный", "neutral": "Нейтральный"}
    platform_map = {"wb": "Wildberries", "ozon": "Ozon", "ym": "Яндекс.Маркет",
                    "gmaps": "Google Maps", "2gis": "2ГИС", "zoon": "Zoon", "ratescan": "РейтСкан"}

    row_num = 2
    for product in profile.products:
        for r in sorted(product.reviews, key=lambda x: x.created_at, reverse=True):
            fill = PatternFill("solid", fgColor=(
                "F0FDF4" if r.sentiment == "positive"
                else "FEF2F2" if r.sentiment == "negative"
                else "F9FAFB"
            ))
            row_data = [
                r.created_at.strftime("%d.%m.%Y"),
                product.name,
                platform_map.get(r.platform, r.platform),
                r.author_name,
                r.rating,
                sentiment_map.get(r.sentiment, r.sentiment),
                r.topics or "",
                r.text,
                r.response.text if r.response else "",
            ]
            for col_num, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_num, column=col_num, value=value)
                cell.fill = fill
                cell.border = cell_border
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            row_num += 1

    # Column widths
    col_widths = [12, 30, 18, 16, 8, 14, 24, 60, 40]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    ws.row_dimensions[1].height = 20
    ws.freeze_panes = "A2"

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    safe_name = profile.brand_name.replace(" ", "_").replace("«", "").replace("»", "")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=reviews_{safe_name}.xlsx"},
    )


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
    if not profile or not profile.products:
        return []

    category = profile.products[0].category
    all_products = db.query(models.Product).filter(models.Product.category == category).all()

    result = []
    for p in all_products:
        reviews = p.reviews
        total = len(reviews)
        avg = round(sum(r.rating for r in reviews) / total, 1) if total else 0
        positive = sum(1 for r in reviews if r.sentiment == "positive")
        negative = sum(1 for r in reviews if r.sentiment == "negative")
        topics: dict = defaultdict(int)
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


@router.get("/category-ranking")
def category_ranking(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    profile = current_user.business
    if not profile or not profile.products:
        return {"brands": [], "monthly_rank": [], "category": ""}

    category = profile.products[0].category
    all_products = db.query(models.Product).filter(models.Product.category == category).all()

    brands = []
    for p in all_products:
        reviews = p.reviews
        total = len(reviews)
        avg = p.avg_rating
        positive = sum(1 for r in reviews if r.sentiment == "positive")
        responded = sum(1 for r in reviews if r.response)
        brands.append({
            "id": p.id,
            "name": p.name,
            "brand": p.brand,
            "is_mine": p.business_id == profile.id,
            "avg_rating": avg,
            "total_reviews": total,
            "positive_pct": round(positive / max(total, 1) * 100),
            "response_rate": round(responded / max(total, 1) * 100),
        })

    # Compute ranks for each metric (1 = best)
    for metric in ["avg_rating", "total_reviews", "positive_pct", "response_rate"]:
        for idx, b in enumerate(sorted(brands, key=lambda x: -x[metric])):
            b[f"rank_{metric}"] = idx + 1

    # My current rank by avg_rating
    my_brand = next((b for b in brands if b["is_mine"]), None)
    base_rank = my_brand["rank_avg_rating"] if my_brand else 1

    # Monthly rank simulation (last 6 months)
    now = datetime.utcnow()
    monthly = []
    n = len(brands)
    offsets = [min(n, max(1, base_rank + d)) for d in [2, 1, 1, 0, 0, 0]]
    for i in range(5, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        monthly.append({
            "month": month_start.strftime("%b %Y"),
            "rank": offsets[5 - i],
            "total": n,
        })

    return {
        "brands": sorted(brands, key=lambda x: x["rank_avg_rating"]),
        "monthly_rank": monthly,
        "category": category,
        "my_brand": my_brand,
    }


@router.get("/problems")
def problems_analysis(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    profile = current_user.business
    if not profile or not profile.products:
        return {"my_problems": {}, "competitor_problems": {}}

    category = profile.products[0].category
    cutoff = datetime.utcnow() - timedelta(days=30)

    # My recent problems
    my_problems: dict = defaultdict(lambda: {"count": 0, "examples": [], "platforms": defaultdict(int)})
    for product in profile.products:
        for r in product.reviews:
            if r.sentiment == "negative" and r.created_at >= cutoff and r.topics:
                for t in r.topics.split(","):
                    t = t.strip()
                    my_problems[t]["count"] += 1
                    my_problems[t]["platforms"][r.platform] += 1
                    if len(my_problems[t]["examples"]) < 2:
                        my_problems[t]["examples"].append(r.text[:120])

    # Also include non-recent negatives if no recent ones
    if not my_problems:
        for product in profile.products:
            for r in product.reviews:
                if r.sentiment == "negative" and r.topics:
                    for t in r.topics.split(","):
                        t = t.strip()
                        my_problems[t]["count"] += 1
                        if len(my_problems[t]["examples"]) < 2:
                            my_problems[t]["examples"].append(r.text[:120])

    # Competitor problems
    comp_data: dict = defaultdict(lambda: defaultdict(int))
    all_cat = db.query(models.Product).filter(
        models.Product.category == category,
        models.Product.business_id != profile.id,
    ).all()
    for p in all_cat:
        for r in p.reviews:
            if r.sentiment == "negative" and r.topics:
                for t in r.topics.split(","):
                    comp_data[p.brand][t.strip()] += 1

    return {
        "my_problems": {
            k: {**v, "platforms": dict(v["platforms"])}
            for k, v in sorted(my_problems.items(), key=lambda x: -x[1]["count"])
        },
        "competitor_problems": {
            brand: dict(sorted(topics.items(), key=lambda x: -x[1])[:5])
            for brand, topics in comp_data.items()
        },
        "period_days": 30,
    }


@router.get("/strengths")
def strengths_analysis(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    profile = current_user.business
    if not profile or not profile.products:
        return {"my_strengths": {}, "competitor_strengths": {}}

    category = profile.products[0].category

    # My strengths
    my_strengths: dict = defaultdict(lambda: {"count": 0, "examples": []})
    for product in profile.products:
        for r in product.reviews:
            if r.sentiment == "positive" and r.topics:
                for t in r.topics.split(","):
                    t = t.strip()
                    my_strengths[t]["count"] += 1
                    if len(my_strengths[t]["examples"]) < 2:
                        my_strengths[t]["examples"].append(r.text[:120])

    # Competitor strengths
    comp_data: dict = defaultdict(lambda: defaultdict(int))
    all_cat = db.query(models.Product).filter(
        models.Product.category == category,
        models.Product.business_id != profile.id,
    ).all()
    for p in all_cat:
        for r in p.reviews:
            if r.sentiment == "positive" and r.topics:
                for t in r.topics.split(","):
                    comp_data[p.brand][t.strip()] += 1

    # Unique advantages: where my count is highest
    my_totals = {k: v["count"] for k, v in my_strengths.items()}
    comp_totals: dict = defaultdict(int)
    for brand_topics in comp_data.values():
        for topic, cnt in brand_topics.items():
            comp_totals[topic] += cnt
    n_competitors = max(len(comp_data), 1)
    unique_advantages = [
        k for k, v in my_totals.items()
        if v > comp_totals.get(k, 0) / n_competitors
    ]

    return {
        "my_strengths": dict(sorted(my_strengths.items(), key=lambda x: -x[1]["count"])),
        "competitor_strengths": {
            brand: dict(sorted(topics.items(), key=lambda x: -x[1])[:5])
            for brand, topics in comp_data.items()
        },
        "unique_advantages": unique_advantages,
        "category": category,
    }


# ===== B2B SURVEY MANAGEMENT =====

class SurveyQuestionCreate(BaseModel):
    question_text: str
    question_type: str  # "choice", "rating", "text"
    options: Optional[List[str]] = None


class SurveyCreate(BaseModel):
    title: str
    description: str
    target_audience: Optional[List[str]] = None  # product categories
    points_reward: int = 25
    estimated_minutes: int = 3
    questions: List[SurveyQuestionCreate]


@router.get("/surveys")
def list_my_surveys(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    profile = current_user.business
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")

    surveys = db.query(models.Survey).filter(models.Survey.business_id == profile.id).all()
    return [
        {
            "id": s.id,
            "title": s.title,
            "description": s.description,
            "target_audience": json.loads(s.target_audience) if s.target_audience else [],
            "points_reward": s.points_reward,
            "estimated_minutes": s.estimated_minutes,
            "is_active": s.is_active,
            "question_count": len(s.questions),
            "completion_count": len(s.completions),
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sorted(surveys, key=lambda x: x.id, reverse=True)
    ]


@router.post("/surveys")
def create_survey(
    data: SurveyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    profile = current_user.business
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль не найден")

    survey = models.Survey(
        title=data.title,
        description=data.description,
        business_id=profile.id,
        category=profile.category,
        target_audience=json.dumps(data.target_audience) if data.target_audience else None,
        points_reward=data.points_reward,
        estimated_minutes=data.estimated_minutes,
        is_active=True,
        gradient="from-indigo-500 to-purple-600",
    )
    db.add(survey)
    db.flush()

    for idx, q in enumerate(data.questions):
        question = models.SurveyQuestion(
            survey_id=survey.id,
            order=idx,
            question_text=q.question_text,
            question_type=q.question_type,
            options=json.dumps(q.options) if q.options else None,
        )
        db.add(question)

    db.commit()
    db.refresh(survey)
    return {"status": "ok", "survey_id": survey.id, "message": "Опрос создан"}


@router.post("/surveys/{survey_id}/toggle")
def toggle_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    profile = current_user.business
    survey = db.query(models.Survey).filter(
        models.Survey.id == survey_id,
        models.Survey.business_id == profile.id,
    ).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Опрос не найден")
    survey.is_active = not survey.is_active
    db.commit()
    return {"status": "ok", "is_active": survey.is_active}


@router.delete("/surveys/{survey_id}")
def delete_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    profile = current_user.business
    survey = db.query(models.Survey).filter(
        models.Survey.id == survey_id,
        models.Survey.business_id == profile.id,
    ).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Опрос не найден")
    db.delete(survey)
    db.commit()
    return {"status": "ok"}
