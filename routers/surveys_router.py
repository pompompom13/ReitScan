import json
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
import models, auth
import random


class GameRewardIn(BaseModel):
    points: int

router = APIRouter(prefix="/api/surveys", tags=["surveys"])


@router.get("")
def list_surveys(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    surveys = db.query(models.Survey).filter(models.Survey.is_active == True).all()
    completed_ids = {sc.survey_id for sc in current_user.survey_completions}
    return [
        {
            "id": s.id,
            "title": s.title,
            "description": s.description,
            "category": s.category,
            "points_reward": s.points_reward,
            "estimated_minutes": s.estimated_minutes,
            "gradient": s.gradient,
            "question_count": len(s.questions),
            "already_completed": s.id in completed_ids,
        }
        for s in surveys
    ]


@router.get("/{survey_id}")
def get_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    s = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Опрос не найден")

    questions = []
    for q in s.questions:
        options = None
        if q.options:
            try:
                options = json.loads(q.options)
            except Exception:
                options = q.options.split(",")
        questions.append({
            "id": q.id,
            "order": q.order,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "options": options,
        })

    already_completed = db.query(models.SurveyCompletion).filter(
        models.SurveyCompletion.survey_id == survey_id,
        models.SurveyCompletion.user_id == current_user.id,
    ).first() is not None

    return {
        "id": s.id,
        "title": s.title,
        "description": s.description,
        "points_reward": s.points_reward,
        "estimated_minutes": s.estimated_minutes,
        "already_completed": already_completed,
        "questions": questions,
    }


@router.post("/{survey_id}/complete")
def complete_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    s = db.query(models.Survey).filter(models.Survey.id == survey_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Опрос не найден")

    already = db.query(models.SurveyCompletion).filter(
        models.SurveyCompletion.survey_id == survey_id,
        models.SurveyCompletion.user_id == current_user.id,
    ).first()
    if already:
        raise HTTPException(status_code=400, detail="Опрос уже пройден")

    completion = models.SurveyCompletion(
        survey_id=survey_id,
        user_id=current_user.id,
        points_earned=s.points_reward,
    )
    db.add(completion)
    current_user.points += s.points_reward
    db.commit()

    return {
        "status": "ok",
        "points_earned": s.points_reward,
        "total_points": current_user.points,
        "message": f"Опрос завершён! Вы получили {s.points_reward} баллов.",
    }


@router.post("/daily-spin")
def daily_spin(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    today = date.today()
    if current_user.last_daily_spin and current_user.last_daily_spin.date() == today:
        raise HTTPException(status_code=400, detail="Уже крутили сегодня")

    # Weighted prize table
    prizes = [
        {"label": "5 баллов", "points": 5, "weight": 30},
        {"label": "10 баллов", "points": 10, "weight": 25},
        {"label": "15 баллов", "points": 15, "weight": 20},
        {"label": "20 баллов", "points": 20, "weight": 12},
        {"label": "25 баллов", "points": 25, "weight": 8},
        {"label": "50 баллов", "points": 50, "weight": 4},
        {"label": "0 баллов", "points": 0, "weight": 1},
    ]
    weights = [p["weight"] for p in prizes]
    prize = random.choices(prizes, weights=weights, k=1)[0]

    current_user.last_daily_spin = datetime.utcnow()
    current_user.points += prize["points"]
    db.commit()

    return {
        "status": "ok",
        "prize_label": prize["label"],
        "points_earned": prize["points"],
        "total_points": current_user.points,
    }


@router.post("/game-reward")
def game_reward(
    body: GameRewardIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    MAX_DAILY = 100
    today = date.today()
    last = current_user.last_game_play
    if last and last.date() == today:
        already = current_user.game_points_today or 0
    else:
        already = 0
        current_user.game_points_today = 0

    pts = max(0, min(body.points, MAX_DAILY - already))
    if pts <= 0:
        return {"status": "ok", "points_earned": 0, "total_points": current_user.points, "message": "Дневной лимит игры исчерпан"}

    current_user.points += pts
    current_user.game_points_today = already + pts
    current_user.last_game_play = datetime.utcnow()
    db.commit()
    return {"status": "ok", "points_earned": pts, "total_points": current_user.points}
