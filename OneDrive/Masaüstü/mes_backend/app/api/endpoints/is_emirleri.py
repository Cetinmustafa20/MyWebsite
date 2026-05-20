from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.db.database import get_db
from app.models.models import IsEmri, MakineIsEmri, Kullanici
from app.core.security import get_current_user, require_yonetici, require_admin

router = APIRouter(prefix="/is-emirleri", tags=["is-emirleri"])


class IsEmriCreate(BaseModel):
    stok_id: int
    cari_id: Optional[int] = None
    miktar: int
    planlanan_baslangic: Optional[datetime] = None
    planlanan_bitis: Optional[datetime] = None
    notlar: Optional[str] = None
    # Hangi makinelerde, hangi sırayla işlenecek
    makine_sirasi: List[int] = []   # [makine_id, makine_id, ...]


class IsEmriOut(BaseModel):
    id: int
    is_emri_no: str
    stok_id: int
    cari_id: Optional[int]
    miktar: int
    durum: str
    planlanan_baslangic: Optional[datetime]
    planlanan_bitis: Optional[datetime]
    olusturma_tarihi: datetime

    class Config:
        from_attributes = True


def _yeni_is_emri_no(db: Session) -> str:
    """IE-2024-00001 formatında artan numara üret."""
    yil = datetime.utcnow().year
    son = (
        db.query(IsEmri)
        .filter(IsEmri.is_emri_no.like(f"IE-{yil}-%"))
        .order_by(IsEmri.id.desc())
        .first()
    )
    if son:
        numara = int(son.is_emri_no.split("-")[-1]) + 1
    else:
        numara = 1
    return f"IE-{yil}-{numara:05d}"


@router.get("/", response_model=List[IsEmriOut])
def list_is_emirleri(
    durum: Optional[str] = None,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    q = db.query(IsEmri)
    if durum:
        q = q.filter(IsEmri.durum == durum)
    return q.order_by(IsEmri.id.desc()).limit(200).all()


@router.get("/{is_emri_id}", response_model=IsEmriOut)
def get_is_emri(
    is_emri_id: int,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    ie = db.query(IsEmri).filter(IsEmri.id == is_emri_id).first()
    if not ie:
        raise HTTPException(status_code=404, detail="İş emri bulunamadı")
    return ie


@router.post("/", response_model=IsEmriOut)
def create_is_emri(
    body: IsEmriCreate,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    """
    Yönetici iş emri oluşturur ve makinelere atar.
    makine_sirasi = [3, 5] → önce M03, sonra M05.
    """
    ie = IsEmri(
        is_emri_no=_yeni_is_emri_no(db),
        stok_id=body.stok_id,
        cari_id=body.cari_id,
        miktar=body.miktar,
        planlanan_baslangic=body.planlanan_baslangic,
        planlanan_bitis=body.planlanan_bitis,
        notlar=body.notlar,
        durum="bekliyor",
        olusturan_id=current_user.id,
    )
    db.add(ie)
    db.flush()  # id al

    for sira, makine_id in enumerate(body.makine_sirasi, start=1):
        mie = MakineIsEmri(
            is_emri_id=ie.id,
            makine_id=makine_id,
            sira_no=sira,
            durum="bekliyor",
        )
        db.add(mie)

    db.commit()
    db.refresh(ie)
    return ie


@router.delete("/{is_emri_id}")
def iptal_is_emri(
    is_emri_id: int,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    ie = db.query(IsEmri).filter(IsEmri.id == is_emri_id).first()
    if not ie:
        raise HTTPException(status_code=404, detail="İş emri bulunamadı")
    if ie.durum in ("tamamlandi",):
        raise HTTPException(status_code=400, detail="Tamamlanmış iş emri iptal edilemez")
    ie.durum = "iptal"
    ie.guncelleme_tarihi = datetime.utcnow()
    db.commit()
    return {"detail": "İş emri iptal edildi"}