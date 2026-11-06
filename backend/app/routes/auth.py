import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.database.session import get_db
from app.models.models import User
from app.schemas.auth import ForgotIn, LoginIn, RegisterIn, ResetIn
from app.services.audit import log_action

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("devopspulse.auth")


def user_out(user: User) -> dict:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "organization_id": user.organization_id,
        "organization_name": user.organization.name if user.organization else None,
        "onboarded": user.organization_id is not None,
    }


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(full_name=body.full_name.strip(), email=email, hashed_password=hash_password(body.password))
    db.add(user)
    db.flush()
    log_action(db, None, user.id, "auth.register")
    db.commit()
    return {"access_token": create_token(user.id), "user": user_out(user)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    minutes = 60 * 24 * 30 if body.remember_me else settings.access_token_expire_minutes
    log_action(db, user.organization_id, user.id, "auth.login")
    db.commit()
    return {"access_token": create_token(user.id, minutes), "user": user_out(user)}


@router.post("/forgot-password")
def forgot_password(body: ForgotIn, db: Session = Depends(get_db)):
    # Always the same response so the endpoint can't be used to discover which emails exist.
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user:
        token = create_token(user.id, minutes=30, purpose="reset")
        link = f"{settings.frontend_origin}/reset-password?token={token}"
        # No email provider is wired up: the link is printed to the server console for local/demo use.
        log.warning("Password reset link for %s: %s", user.email, link)
        log_action(db, user.organization_id, user.id, "auth.forgot_password")
        db.commit()
    return {"message": "If an account exists for that email, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    sub = decode_token(body.token, purpose="reset")
    user = db.get(User, int(sub)) if sub and sub.isdigit() else None
    if not user:
        raise HTTPException(400, "This reset link is invalid or has expired")
    user.hashed_password = hash_password(body.new_password)
    log_action(db, user.organization_id, user.id, "auth.reset_password")
    db.commit()
    return {"message": "Password updated. You can now sign in."}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)
