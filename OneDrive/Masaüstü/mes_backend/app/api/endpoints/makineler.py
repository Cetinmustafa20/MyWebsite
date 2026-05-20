from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.db.database import get_db
from app.models.models import Makine, Kullanici
from app.core.security import get_current_user, require_admin
from app.services.makine_service import get_tum_makine_durumlari, get_makine_durumu_redis

router = APIRouter(prefix="/makineler", tags=["makineler"])


# ---- Pydantic şemaları ----

class MakineCreate(BaseModel):
    kod: str
    ad: str
    aciklama: Optional[str] = None
    birim_sure_saniye: Optional[int] = None


class MakineUpdate(BaseModel):
    ad: Optional[str] = None
    aciklama: Optional[str] = None
    aktif: Optional[bool] = None
    birim_sure_saniye: Optional[int] = None


class MakineOut(BaseModel):
    id: int
    kod: str
    ad: str
    aciklama: Optional[str]
    durum: str
    aktif: bool
    birim_sure_saniye: Optional[int] = None

    class Config:
        from_attributes = True


class MakineDurumOut(BaseModel):
    makine_id: int
    kod: str
    ad: str
    durum: str
    guncelleme: Optional[str]
    is_emri_id: Optional[int]
    baslangic_zamani: Optional[str]
    uretimde_dakika: Optional[int] = None
    ariza_tipi: Optional[str]
    ariza_aciklama: Optional[str]
    ariza_baslangic: Optional[str]
    ariza_dakika: Optional[int] = None


# ---- Endpoint'ler ----


@router.get("/public", response_model=List[MakineOut])
def list_makineler_public(db: Session = Depends(get_db)):
    """Token gerektirmeyen makine listesi - login ekranı için."""
    return db.query(Makine).filter(Makine.aktif == True).order_by(Makine.kod).all()

@router.get("/", response_model=List[MakineOut])
def list_makineler(
    aktif_only: bool = True,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    q = db.query(Makine)
    if aktif_only:
        q = q.filter(Makine.aktif == True)
    return q.order_by(Makine.kod).all()


@router.get("/durum", response_model=List[MakineDurumOut])
def tum_makine_durumlari(_: Kullanici = Depends(get_current_user)):
    durumlar = get_tum_makine_durumlari()
    result = []
    now = datetime.utcnow()

    for d in durumlar:
        uretimde_dakika = None
        if d.get("baslangic_zamani"):
            try:
                bs = datetime.fromisoformat(d["baslangic_zamani"])
                uretimde_dakika = int((now - bs).total_seconds() / 60)
            except Exception:
                pass

        ariza_dakika = None
        if d.get("ariza_baslangic"):
            try:
                ab = datetime.fromisoformat(d["ariza_baslangic"])
                ariza_dakika = int((now - ab).total_seconds() / 60)
            except Exception:
                pass

        result.append(MakineDurumOut(
            makine_id=d.get("makine_id"),
            kod=d.get("kod"),
            ad=d.get("ad"),
            durum=d.get("durum"),
            guncelleme=d.get("guncelleme"),
            is_emri_id=d.get("is_emri_id"),
            baslangic_zamani=d.get("baslangic_zamani"),
            uretimde_dakika=uretimde_dakika,
            ariza_tipi=d.get("ariza_tipi"),
            ariza_aciklama=d.get("ariza_aciklama"),
            ariza_baslangic=d.get("ariza_baslangic"),
            ariza_dakika=ariza_dakika,
        ))

    return result

@router.get("/{makine_id}/durum", response_model=MakineDurumOut)
def makine_durum(
    makine_id: int,
    _: Kullanici = Depends(get_current_user),
):
    data = get_makine_durumu_redis(makine_id)
    if not data:
        raise HTTPException(status_code=404, detail="Makine durumu bulunamadı")
    return MakineDurumOut(**data)


@router.post("/", response_model=MakineOut)
def create_makine(
    body: MakineCreate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_admin),
):
    if db.query(Makine).filter(Makine.kod == body.kod).first():
        raise HTTPException(status_code=400, detail="Bu kod zaten kayıtlı")
    makine = Makine(**body.model_dump())
    db.add(makine)
    db.commit()
    db.refresh(makine)
    return makine


@router.patch("/{makine_id}", response_model=MakineOut)
def update_makine(
    makine_id: int,
    body: MakineUpdate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_admin),
):
    makine = db.query(Makine).filter(Makine.id == makine_id).first()
    if not makine:
        raise HTTPException(status_code=404, detail="Makine bulunamadı")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(makine, field, value)
    makine.guncelleme_tarihi = datetime.utcnow()
    db.commit()
    db.refresh(makine)
    return makine