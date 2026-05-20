from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gecersiz veya suresi dolmus token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def extract_bearer_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()

    cookie_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    if cookie_token:
        return cookie_token

    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
):
    from app.models.models import Kullanici

    token = extract_bearer_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik dogrulamasi gerekli",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    kullanici_id: Optional[str] = payload.get("sub")
    if kullanici_id is None:
        raise HTTPException(status_code=401, detail="Gecersiz token")

    kullanici = db.query(Kullanici).filter(
        Kullanici.id == int(kullanici_id),
        Kullanici.aktif == True,
    ).first()

    if not kullanici:
        raise HTTPException(status_code=401, detail="Kullanici bulunamadi")
    return kullanici


def require_admin(current_user=Depends(get_current_user)):
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="Bu islem icin admin yetkisi gerekli")
    return current_user


def require_yonetici(current_user=Depends(get_current_user)):
    if current_user.rol not in ("admin", "yonetici"):
        raise HTTPException(status_code=403, detail="Yetkiniz yok")
    return current_user
