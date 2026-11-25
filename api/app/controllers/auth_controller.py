"""Authentication and user profile controller."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.auth import (
    create_access_token,
    get_current_user,
    get_token_secret,
    hash_password,
    normalize_email,
    verify_password,
)
from ..core.database import get_db
from ..models import User
from ..schemas import (
    LoginInput,
    ProfileUpdateInput,
    RegisterInput,
    TokenOutput,
    UserOutput,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def _user_output(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "full_name": user.full_name,
        "email": user.email,
        "phone_number": user.phone_number,
        "role": user.role or "FARMER",
    }


def _token_output(user: User) -> dict:
    token, expires_in = create_access_token(user.user_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": _user_output(user),
    }


@router.post("/register", status_code=201, response_model=TokenOutput)
def register(body: RegisterInput, db: Session = Depends(get_db)):
    get_token_secret()
    try:
        email = normalize_email(body.email)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if not body.full_name.strip():
        raise HTTPException(status_code=422, detail="full_name không được để trống")
    duplicate = (
        db.query(User).filter(func.lower(func.trim(User.email)) == email).first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Email đã được đăng ký")

    user = User(
        user_id=str(uuid.uuid4()),
        full_name=body.full_name.strip(),
        email=email,
        phone_number=body.phone_number.strip() if body.phone_number else None,
        password_hash=hash_password(body.password),
        role="FARMER",
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email đã được đăng ký") from None
    return _token_output(user)


@router.post("/login", response_model=TokenOutput)
def login(body: LoginInput, db: Session = Depends(get_db)):
    get_token_secret()
    try:
        email = normalize_email(body.email)
    except ValueError:
        email = "invalid-address"
    user = db.query(User).filter(func.lower(func.trim(User.email)) == email).first()
    password_matches = verify_password(
        body.password, user.password_hash if user is not None else None
    )
    if user is None or not password_matches:
        raise HTTPException(
            status_code=401,
            detail="Email hoặc mật khẩu không đúng",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _token_output(user)


@router.get("/me", response_model=UserOutput)
def get_profile(current_user: User = Depends(get_current_user)):
    return _user_output(current_user)


@router.patch("/me", response_model=UserOutput)
def update_profile(
    body: ProfileUpdateInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=422, detail="Không có trường hồ sơ cần cập nhật"
        )
    if "full_name" in changes:
        full_name = (changes["full_name"] or "").strip()
        if not full_name:
            raise HTTPException(status_code=422, detail="full_name không được để trống")
        current_user.full_name = full_name
    if "phone_number" in changes:
        current_user.phone_number = (
            changes["phone_number"].strip() if changes["phone_number"] else None
        )
    db.commit()
    db.refresh(current_user)
    return _user_output(current_user)
