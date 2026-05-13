from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models, schemas, auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.Token)
def register(data: schemas.UserRegister, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    user = models.User(
        email=data.email,
        username=data.username,
        hashed_password=auth.get_password_hash(data.password),
        user_type=data.user_type,
        company_name=data.company_name,
        company_category=data.company_category,
        points=0,
    )
    db.add(user)
    db.flush()

    if data.user_type == "b2b" and data.company_name:
        profile = models.BusinessProfile(
            user_id=user.id,
            brand_name=data.company_name,
            category=data.company_category or "Другое",
        )
        db.add(profile)

    db.commit()
    db.refresh(user)

    token = auth.create_access_token({"sub": str(user.id)})
    return schemas.Token(
        access_token=token,
        token_type="bearer",
        user_type=user.user_type,
        username=user.username,
    )


@router.post("/login", response_model=schemas.Token)
def login(data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user or not auth.verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    token = auth.create_access_token({"sub": str(user.id)})
    return schemas.Token(
        access_token=token,
        token_type="bearer",
        user_type=user.user_type,
        username=user.username,
    )


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user
