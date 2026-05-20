"""
Tablet'ten gelen uretim aksiyonlari.
Operator: baslat, bitir, ariza bildir, is emri kabul/red.
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.models import (
    Ariza,
    BakimPlani,
    IsEmri,
    KaliteKontrol,
    Kullanici,
    Makine,
    MakineIsEmri,
    Operator,
    OperatorMakineYetki,
    TabletKaydi,
    UretimLog,
)
from app.services import makine_service

router = APIRouter(prefix="/uretim", tags=["uretim"])


class UretimBaslatRequest(BaseModel):
    makine_is_emri_id: int


class UretimBitirRequest(BaseModel):
    makine_is_emri_id: int


class ArizaBildirRequest(BaseModel):
    makine_id: int
    ariza_tipi: str
    aciklama: Optional[str] = None


class IsEmriKabulRequest(BaseModel):
    makine_is_emri_id: int
    kabul: bool


class TabletBaglaRequest(BaseModel):
    tablet_id: str
    makine_id: int
    tablet_adi: Optional[str] = None


class SonUretimOut(BaseModel):
    makine_is_emri_id: int
    is_emri_no: str
    durum: str
    stok_adi: str
    bitis_zamani: Optional[datetime]
    operator_adi: Optional[str]


class BakimUyariOut(BaseModel):
    id: int
    bakim_adi: str
    bakim_tipi: str
    sonraki_bakim: Optional[datetime]
    durum: str


class TabletBaglantiOut(BaseModel):
    id: int
    tablet_id: str
    tablet_adi: Optional[str]
    makine_id: int
    makine_kodu: str
    makine_adi: str
    makine_durum: str
    son_aktivite: Optional[datetime]
    aktif: bool
    yetkili: bool
    acik_ariza: Optional[str] = None
    aktif_bakim: Optional[BakimUyariOut] = None
    son_uretimler: List[SonUretimOut] = []


class MakineIsEmriOut(BaseModel):
    id: int
    is_emri_id: int
    makine_id: int
    operator_id: Optional[int]
    durum: str
    baslangic_zamani: Optional[datetime]
    bitis_zamani: Optional[datetime]

    class Config:
        from_attributes = True


class ArizaOut(BaseModel):
    id: int
    makine_id: int
    ariza_tipi: str
    aciklama: Optional[str]
    baslangic: datetime
    durum: str

    class Config:
        from_attributes = True


class BekleyenIsEmriOut(BaseModel):
    makine_is_emri_id: int
    is_emri_no: str
    stok_adi: str
    miktar: int
    planlanan_baslangic: Optional[datetime]


class MakineSecimOut(BaseModel):
    id: int
    kod: str
    ad: str
    durum: str
    yetkili: bool
    aktif_tablet_var: bool


def get_operator(kullanici: Kullanici, db: Session) -> Operator:
    operator = db.query(Operator).filter(
        Operator.kullanici_id == kullanici.id,
        Operator.aktif == True,
    ).first()
    if not operator:
        raise HTTPException(status_code=403, detail="Operator kaydi bulunamadi")
    return operator


def operator_makine_yetkili_mi(db: Session, operator_id: int, makine_id: int) -> bool:
    return db.query(OperatorMakineYetki).filter(
        OperatorMakineYetki.operator_id == operator_id,
        OperatorMakineYetki.makine_id == makine_id,
        OperatorMakineYetki.aktif == True,
    ).first() is not None


def require_machine_access(db: Session, operator: Operator, makine_id: int):
    if not operator_makine_yetkili_mi(db, operator.id, makine_id):
        raise HTTPException(status_code=403, detail="Bu makinede calisma yetkiniz yok")


def tablet_baglanti_detayi_olustur(db: Session, tablet: TabletKaydi, operator: Operator) -> TabletBaglantiOut:
    makine = db.query(Makine).filter(Makine.id == tablet.makine_id).first()
    yetkili = operator_makine_yetkili_mi(db, operator.id, tablet.makine_id)

    acik_ariza_kaydi = db.query(Ariza).filter(
        Ariza.makine_id == tablet.makine_id,
        Ariza.durum == "devam_ediyor",
    ).order_by(Ariza.baslangic.desc()).first()

    aktif_bakim_plan = db.query(BakimPlani).filter(
        BakimPlani.makine_id == tablet.makine_id,
        BakimPlani.aktif == True,
    ).order_by(BakimPlani.sonraki_bakim.asc()).first()

    bakim_uyari = None
    if aktif_bakim_plan:
      durum = "planli"
      if aktif_bakim_plan.sonraki_bakim and aktif_bakim_plan.sonraki_bakim < datetime.utcnow():
          durum = "gecikmis"
      bakim_uyari = BakimUyariOut(
          id=aktif_bakim_plan.id,
          bakim_adi=aktif_bakim_plan.bakim_adi,
          bakim_tipi=aktif_bakim_plan.bakim_tipi,
          sonraki_bakim=aktif_bakim_plan.sonraki_bakim,
          durum=durum,
      )

    tamamlananlar = db.query(MakineIsEmri).filter(
        MakineIsEmri.makine_id == tablet.makine_id,
        MakineIsEmri.bitis_zamani != None,
    ).order_by(MakineIsEmri.bitis_zamani.desc()).limit(5).all()

    son_uretimler = []
    for kayit in tamamlananlar:
        is_emri = db.query(IsEmri).filter(IsEmri.id == kayit.is_emri_id).first()
        operator_adi = None
        if kayit.operator_id:
            kayit_operator = db.query(Operator).filter(Operator.id == kayit.operator_id).first()
            if kayit_operator and kayit_operator.kullanici:
                operator_adi = kayit_operator.kullanici.ad_soyad
        son_uretimler.append(SonUretimOut(
            makine_is_emri_id=kayit.id,
            is_emri_no=is_emri.is_emri_no if is_emri else "-",
            durum=kayit.durum,
            stok_adi=is_emri.stok.stok_adi if is_emri and is_emri.stok else "-",
            bitis_zamani=kayit.bitis_zamani,
            operator_adi=operator_adi,
        ))

    return TabletBaglantiOut(
        id=tablet.id,
        tablet_id=tablet.tablet_id,
        tablet_adi=tablet.tablet_adi,
        makine_id=tablet.makine_id,
        makine_kodu=makine.kod if makine else "-",
        makine_adi=makine.ad if makine else "-",
        makine_durum=makine.durum if makine else "bilinmiyor",
        son_aktivite=tablet.son_aktivite,
        aktif=tablet.aktif,
        yetkili=yetkili,
        acik_ariza=acik_ariza_kaydi.aciklama if acik_ariza_kaydi else None,
        aktif_bakim=bakim_uyari,
        son_uretimler=son_uretimler,
    )


@router.get("/tablet/makineler", response_model=List[MakineSecimOut])
def tablet_makine_listesi(
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    operator = get_operator(current_user, db)
    aktif_makineler = db.query(Makine).filter(Makine.aktif == True).order_by(Makine.kod).all()
    result = []
    for makine in aktif_makineler:
        yetkili = operator_makine_yetkili_mi(db, operator.id, makine.id)
        aktif_tablet_var = db.query(TabletKaydi).filter(
            TabletKaydi.makine_id == makine.id,
            TabletKaydi.aktif == True,
        ).first() is not None
        result.append(MakineSecimOut(
            id=makine.id,
            kod=makine.kod,
            ad=makine.ad,
            durum=makine.durum,
            yetkili=yetkili,
            aktif_tablet_var=aktif_tablet_var,
        ))
    return result


@router.post("/tablet/bagla", response_model=TabletBaglantiOut)
def tablet_bagla(
    body: TabletBaglaRequest,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    operator = get_operator(current_user, db)
    require_machine_access(db, operator, body.makine_id)

    makine = db.query(Makine).filter(Makine.id == body.makine_id, Makine.aktif == True).first()
    if not makine:
        raise HTTPException(status_code=404, detail="Makine bulunamadi")

    mevcut_makine_baglantisi = db.query(TabletKaydi).filter(
        TabletKaydi.makine_id == body.makine_id,
        TabletKaydi.aktif == True,
        TabletKaydi.tablet_id != body.tablet_id,
    ).first()
    if mevcut_makine_baglantisi:
        raise HTTPException(status_code=400, detail="Bu makineye zaten bir tablet bagli")

    tablet = db.query(TabletKaydi).filter(TabletKaydi.tablet_id == body.tablet_id).first()
    if tablet:
        tablet.makine_id = body.makine_id
        tablet.tablet_adi = body.tablet_adi or tablet.tablet_adi or f"Tablet-{makine.kod}"
        tablet.aktif = True
        tablet.son_aktivite = datetime.utcnow()
    else:
        tablet = TabletKaydi(
            tablet_id=body.tablet_id,
            makine_id=body.makine_id,
            tablet_adi=body.tablet_adi or f"Tablet-{makine.kod}",
            son_aktivite=datetime.utcnow(),
            aktif=True,
        )
        db.add(tablet)

    db.commit()
    db.refresh(tablet)
    return tablet_baglanti_detayi_olustur(db, tablet, operator)


@router.get("/tablet/{tablet_id}", response_model=TabletBaglantiOut)
def tablet_baglanti_getir(
    tablet_id: str,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    operator = get_operator(current_user, db)
    tablet = db.query(TabletKaydi).filter(
        TabletKaydi.tablet_id == tablet_id,
        TabletKaydi.aktif == True,
    ).first()
    if not tablet:
        raise HTTPException(status_code=404, detail="Tablet kaydi bulunamadi")

    tablet.son_aktivite = datetime.utcnow()
    db.commit()
    db.refresh(tablet)
    return tablet_baglanti_detayi_olustur(db, tablet, operator)



@router.delete("/tablet/{tablet_id}/baglantiyi-kopar")
def tablet_baglantiyi_kopar(
    tablet_id: str,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    """Tablet bağlantısını kopar — yetkisiz makine seçiminde kullanılır."""
    tablet = db.query(TabletKaydi).filter(
        TabletKaydi.tablet_id == tablet_id,
        TabletKaydi.aktif == True,
    ).first()
    if tablet:
        tablet.aktif = False
        db.commit()
    return {"detail": "Baglanti kesildi"}

@router.get("/bekleyen/{makine_id}", response_model=List[BekleyenIsEmriOut])
def bekleyen_is_emirleri(
    makine_id: int,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    operator = get_operator(current_user, db)
    require_machine_access(db, operator, makine_id)

    rows = (
        db.query(MakineIsEmri, IsEmri)
        .join(IsEmri, IsEmri.id == MakineIsEmri.is_emri_id)
        .filter(
            MakineIsEmri.makine_id == makine_id,
            MakineIsEmri.durum.in_(["bekliyor", "kabul_edildi"]),
        )
        .order_by(MakineIsEmri.sira_no)
        .all()
    )
    return [
        BekleyenIsEmriOut(
            makine_is_emri_id=mie.id,
            is_emri_no=ie.is_emri_no,
            stok_adi=ie.stok.stok_adi,
            miktar=ie.miktar,
            planlanan_baslangic=ie.planlanan_baslangic,
        )
        for mie, ie in rows
    ]


@router.post("/kabul", response_model=MakineIsEmriOut)
def is_emri_kabul_red(
    body: IsEmriKabulRequest,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    operator = get_operator(current_user, db)
    mie = db.query(MakineIsEmri).filter(MakineIsEmri.id == body.makine_is_emri_id).first()
    if not mie:
        raise HTTPException(status_code=404, detail="Is emri bulunamadi")
    require_machine_access(db, operator, mie.makine_id)
    if mie.durum != "bekliyor":
        raise HTTPException(status_code=400, detail=f"Bu is emri zaten '{mie.durum}' durumunda")
    if mie.operator_id and mie.operator_id != operator.id:
        raise HTTPException(status_code=403, detail="Bu is emri baska bir operator tarafindan sahiplenilmis")

    yeni_durum = "kabul_edildi" if body.kabul else "reddedildi"
    mie.durum = yeni_durum
    mie.operator_id = operator.id
    mie.guncelleme_tarihi = datetime.utcnow()

    log = UretimLog(
        makine_is_emri_id=mie.id,
        islem_tipi="is_emri_kabul" if body.kabul else "is_emri_red",
        operator_id=operator.id,
        makine_id=mie.makine_id,
        onceki_durum="bekliyor",
        yeni_durum=yeni_durum,
    )
    db.add(log)
    db.commit()
    db.refresh(mie)
    return mie


@router.post("/baslat", response_model=MakineIsEmriOut)
def uretim_baslat(
    body: UretimBaslatRequest,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    operator = get_operator(current_user, db)
    mie = db.query(MakineIsEmri).filter(MakineIsEmri.id == body.makine_is_emri_id).first()
    if not mie:
        raise HTTPException(status_code=404, detail="Is emri bulunamadi")
    require_machine_access(db, operator, mie.makine_id)
    try:
        result = makine_service.uretim_baslat(db, body.makine_is_emri_id, operator.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/bitir", response_model=MakineIsEmriOut)
def uretim_bitir(
    body: UretimBitirRequest,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    operator = get_operator(current_user, db)
    mie = db.query(MakineIsEmri).filter(MakineIsEmri.id == body.makine_is_emri_id).first()
    if not mie:
        raise HTTPException(status_code=404, detail="Is emri bulunamadi")
    require_machine_access(db, operator, mie.makine_id)
    try:
        result = makine_service.uretim_bitir(db, body.makine_is_emri_id, operator.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/ariza", response_model=ArizaOut)
def ariza_bildir(
    body: ArizaBildirRequest,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    operator = get_operator(current_user, db)
    require_machine_access(db, operator, body.makine_id)
    try:
        ariza = makine_service.ariza_bildir(
            db, body.makine_id, operator.id, body.ariza_tipi, body.aciklama or ""
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ariza


@router.get("/aktif/{makine_id}", response_model=Optional[MakineIsEmriOut])
def aktif_is_emri(
    makine_id: int,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    operator = get_operator(current_user, db)
    require_machine_access(db, operator, makine_id)
    mie = db.query(MakineIsEmri).filter(
        MakineIsEmri.makine_id == makine_id,
        MakineIsEmri.durum.in_(["basladi", "duraklatildi"]),
    ).first()
    if mie and mie.operator_id and mie.operator_id != operator.id:
        raise HTTPException(status_code=403, detail="Bu makinedeki aktif uretim kaydina erisemezsiniz")
    return mie