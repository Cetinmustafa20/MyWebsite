from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.models import Kullanici
from app.core.security import verify_password, create_access_token, get_current_user
from app.core.config import settings
from app.services.audit_service import audit_log_ekle

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


class SessionInfo(BaseModel):
    kullanici_id: int
    ad_soyad: str
    rol: str


class KullaniciMe(BaseModel):
    id: int
    ad_soyad: str
    kullanici_adi: str
    rol: str

    class Config:
        from_attributes = True


def _set_auth_cookie(request: Request, response: Response, token: str) -> None:
    host = request.url.hostname or ""
    is_local = host in {"localhost", "127.0.0.1"}
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE or (settings.ENFORCE_HTTPS and not is_local),
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


@router.post("/token", response_model=SessionInfo)
@limiter.limit("5/5minute")
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else "bilinmiyor"

    kullanici = db.query(Kullanici).filter(
        Kullanici.kullanici_adi == form_data.username,
        Kullanici.aktif == True,
    ).first()

    if not kullanici or not verify_password(form_data.password, kullanici.sifre_hash):
        audit_log_ekle(
            db=db,
            islem="giris_denemesi",
            detay="Basarisiz giris denemesi",
            kullanici_adi=form_data.username,
            ip_adresi=ip,
            basarili=False,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanici adi veya sifre hatali",
        )

    audit_log_ekle(
        db=db,
        islem="giris",
        detay="Basarili giris",
        kullanici_id=kullanici.id,
        kullanici_adi=kullanici.kullanici_adi,
        rol=kullanici.rol,
        ip_adresi=ip,
        basarili=True,
    )

    token = create_access_token(
        data={"sub": str(kullanici.id), "rol": kullanici.rol},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    _set_auth_cookie(request, response, token)

    return SessionInfo(
        kullanici_id=kullanici.id,
        ad_soyad=kullanici.ad_soyad,
        rol=kullanici.rol,
    )


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/")
    return {"detail": "Cikis yapildi"}


@router.get("/me", response_model=KullaniciMe)
def get_me(current_user: Kullanici = Depends(get_current_user)):
    return current_user
