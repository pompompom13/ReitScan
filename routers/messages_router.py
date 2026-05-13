from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from database import get_db
import models, auth

router = APIRouter(tags=["messages"])


class StartConversation(BaseModel):
    business_id: int
    product_id: Optional[int] = None
    subject: str
    first_message: str


class SendReply(BaseModel):
    text: str


# ─── B2C endpoints ────────────────────────────────────────────────────────────

@router.post("/api/messages/start")
def start_conversation(
    data: StartConversation,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    business = db.query(models.BusinessProfile).filter(
        models.BusinessProfile.id == data.business_id
    ).first()
    if not business:
        raise HTTPException(status_code=404, detail="Компания не найдена")

    conv = models.Conversation(
        b2c_user_id=current_user.id,
        business_id=data.business_id,
        product_id=data.product_id,
        subject=data.subject,
        is_read_b2b=False,
        is_read_b2c=True,
    )
    db.add(conv)
    db.flush()

    msg = models.ConversationMessage(
        conversation_id=conv.id,
        sender_type="b2c",
        sender_name=current_user.username,
        text=data.first_message,
    )
    db.add(msg)
    db.commit()
    db.refresh(conv)

    return {"status": "ok", "conversation_id": conv.id}


@router.get("/api/messages/conversations")
def my_conversations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    convs = (
        db.query(models.Conversation)
        .filter(models.Conversation.b2c_user_id == current_user.id)
        .order_by(models.Conversation.last_message_at.desc())
        .all()
    )
    return [_conv_summary(c, side="b2c") for c in convs]


@router.get("/api/messages/conversations/{conv_id}")
def get_conversation(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
    if not conv or conv.b2c_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Переписка не найдена")

    conv.is_read_b2c = True
    db.commit()

    return _conv_detail(conv)


@router.post("/api/messages/conversations/{conv_id}/reply")
def b2c_reply(
    conv_id: int,
    data: SendReply,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
    if not conv or conv.b2c_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Переписка не найдена")

    msg = models.ConversationMessage(
        conversation_id=conv_id,
        sender_type="b2c",
        sender_name=current_user.username,
        text=data.text,
    )
    db.add(msg)
    conv.last_message_at = datetime.utcnow()
    conv.is_read_b2b = False
    conv.is_read_b2c = True
    db.commit()

    return {"status": "ok"}


# ─── B2B endpoints ────────────────────────────────────────────────────────────

@router.get("/api/b2b/messages/conversations")
def b2b_conversations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    business = db.query(models.BusinessProfile).filter(
        models.BusinessProfile.user_id == current_user.id
    ).first()
    if not business:
        raise HTTPException(status_code=404, detail="Профиль не найден")

    convs = (
        db.query(models.Conversation)
        .filter(models.Conversation.business_id == business.id)
        .order_by(models.Conversation.last_message_at.desc())
        .all()
    )
    return [_conv_summary(c, side="b2b") for c in convs]


@router.get("/api/b2b/messages/conversations/{conv_id}")
def b2b_get_conversation(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    business = db.query(models.BusinessProfile).filter(
        models.BusinessProfile.user_id == current_user.id
    ).first()
    conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
    if not conv or not business or conv.business_id != business.id:
        raise HTTPException(status_code=404, detail="Переписка не найдена")

    conv.is_read_b2b = True
    db.commit()

    return _conv_detail(conv)


@router.post("/api/b2b/messages/conversations/{conv_id}/reply")
def b2b_reply(
    conv_id: int,
    data: SendReply,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_b2b),
):
    business = db.query(models.BusinessProfile).filter(
        models.BusinessProfile.user_id == current_user.id
    ).first()
    conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
    if not conv or not business or conv.business_id != business.id:
        raise HTTPException(status_code=404, detail="Переписка не найдена")

    msg = models.ConversationMessage(
        conversation_id=conv_id,
        sender_type="b2b",
        sender_name=business.brand_name,
        text=data.text,
    )
    db.add(msg)
    conv.last_message_at = datetime.utcnow()
    conv.is_read_b2c = False
    conv.is_read_b2b = True
    db.commit()

    return {"status": "ok"}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _conv_summary(conv: models.Conversation, side: str) -> dict:
    last_msg = conv.messages[-1] if conv.messages else None
    unread = not conv.is_read_b2c if side == "b2c" else not conv.is_read_b2b
    return {
        "id": conv.id,
        "subject": conv.subject,
        "business_name": conv.business.brand_name if conv.business else "—",
        "client_name": conv.b2c_user.username if conv.b2c_user else "—",
        "product_name": conv.product.name if conv.product else None,
        "last_message": last_msg.text[:80] if last_msg else "",
        "last_message_at": conv.last_message_at.isoformat(),
        "unread": unread,
        "message_count": len(conv.messages),
    }


def _conv_detail(conv: models.Conversation) -> dict:
    return {
        "id": conv.id,
        "subject": conv.subject,
        "business_name": conv.business.brand_name if conv.business else "—",
        "client_name": conv.b2c_user.username if conv.b2c_user else "—",
        "product_name": conv.product.name if conv.product else None,
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "sender_name": m.sender_name,
                "text": m.text,
                "created_at": m.created_at.isoformat(),
            }
            for m in conv.messages
        ],
    }
