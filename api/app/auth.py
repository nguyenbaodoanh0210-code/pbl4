"""Password hashing and short-lived HMAC-signed bearer tokens."""

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


TOKEN_ISSUER = "smart-greenhouse-api"
TOKEN_LIFETIME_SECONDS = 60 * 60
PASSWORD_HASH_ITERATIONS = 600_000
bearer_scheme = HTTPBearer(auto_error=False)


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def get_token_secret() -> bytes:
    secret = os.getenv("AUTH_TOKEN_SECRET", "").strip()
    encoded = secret.encode("utf-8")
    if secret.startswith("replace-with-") or len(encoded) < 32:
        raise HTTPException(
            status_code=503,
            detail="AUTH_TOKEN_SECRET phải được cấu hình bằng chuỗi ngẫu nhiên tối thiểu 32 byte",
        )
    return encoded


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
    )
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_HASH_ITERATIONS, _b64url_encode(salt), _b64url_encode(digest)
    )


_DUMMY_PASSWORD_HASH = hash_password("not-a-real-password-used-for-timing")


def verify_password(password: str, encoded_hash: str | None) -> bool:
    candidate = encoded_hash or _DUMMY_PASSWORD_HASH
    try:
        algorithm, iterations, salt, expected = candidate.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(iterations)
        if not 100_000 <= rounds <= 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _b64url_decode(salt), rounds
        )
        matches = hmac.compare_digest(actual, _b64url_decode(expected))
        return bool(encoded_hash) and matches
    except (ValueError, TypeError):
        return False


def normalize_email(email: str) -> str:
    value = email.strip().casefold()
    if len(value) > 254 or value.count("@") != 1:
        raise ValueError("Địa chỉ email không hợp lệ")
    local, domain = value.split("@", 1)
    if (
        not local
        or len(local) > 64
        or not domain
        or "." not in domain
        or any(character.isspace() for character in value)
        or domain.startswith(".")
        or domain.endswith(".")
        or ".." in value
    ):
        raise ValueError("Địa chỉ email không hợp lệ")
    return value


def create_access_token(user_id: str) -> tuple[str, int]:
    secret = get_token_secret()
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": TOKEN_ISSUER,
        "sub": user_id,
        "iat": now,
        "exp": now + TOKEN_LIFETIME_SECONDS,
    }
    signing_input = ".".join(
        (
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode()),
            _b64url_encode(json.dumps(payload, separators=(",", ":")).encode()),
        )
    )
    signature = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(signature)}", TOKEN_LIFETIME_SECONDS


def decode_access_token(token: str) -> str:
    secret = get_token_secret()
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_payload}"
        supplied_signature = _b64url_decode(encoded_signature)
        expected_signature = hmac.new(
            secret, signing_input.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("Invalid signature")
        header = json.loads(_b64url_decode(encoded_header))
        payload = json.loads(_b64url_decode(encoded_payload))
        now = int(time.time())
        if (
            header.get("alg") != "HS256"
            or header.get("typ") != "JWT"
            or payload.get("iss") != TOKEN_ISSUER
            or not isinstance(payload.get("sub"), str)
            or not isinstance(payload.get("exp"), int)
            or isinstance(payload.get("exp"), bool)
            or payload["exp"] <= now
            or not isinstance(payload.get("iat"), int)
            or isinstance(payload.get("iat"), bool)
            or payload["iat"] > now + 60
            or payload["exp"] <= payload["iat"]
            or payload["exp"] - payload["iat"] > TOKEN_LIFETIME_SECONDS
        ):
            raise ValueError("Invalid token claims")
        return payload["sub"]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Token đăng nhập không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Cần đăng nhập để truy cập tài nguyên này",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_access_token(credentials.credentials)
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Tài khoản không còn tồn tại",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
