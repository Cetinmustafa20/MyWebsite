from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.db.database import get_db
from app.models.models import (
    Cari,
    Operator,
    OperatorMakineYetki,
    StokKarti,
    TabletKaydi,
    Kullanici,
)
from app.core.security import get_current_user, require_admin, require_yonetici

router = APIRouter(prefix="/tanimlar", tags=["tanimlar"])


def get_operator_or_403(db: Session, kullanici_id: int) -> Operator:
    operator = db.query(Operator).filter(
        Operator.kullanici_id == kullanici_id,
        Operator.aktif == True,
    ).first()
    if not operator:
        raise HTTPException(403, "Operator kaydi bulunamadi")
    return operator


def operator_makine_yetkili_mi(db: Session, operator_id: int, makine_id: int) -> bool:
    return db.query(OperatorMakineYetki).filter(
        OperatorMakineYetki.operator_id == operator_id,
        OperatorMakineYetki.makine_id == makine_id,
        OperatorMakineYetki.aktif == True,
    ).first() is not None


def require_operator_machine_access(db: Session, kullanici_id: int, makine_id: int) -> Operator:
    operator = get_operator_or_403(db, kullanici_id)
    if not operator_makine_yetkili_mi(db, operator.id, makine_id):
        raise HTTPException(403, "Bu makinede calisma yetkiniz yok")
    return operator


# ── STOK KARTLARI ──────────────────────────────────────────

class StokCreate(BaseModel):
    stok_kodu: str
    stok_adi: str
    birim: str = "ADET"
    kategori: Optional[str] = None
    aciklama: Optional[str] = None

class StokUpdate(BaseModel):
    stok_adi: Optional[str] = None
    birim: Optional[str] = None
    kategori: Optional[str] = None
    aciklama: Optional[str] = None
    aktif: Optional[bool] = None

class StokOut(BaseModel):
    id: int
    stok_kodu: str
    stok_adi: str
    birim: str
    kategori: Optional[str]
    aciklama: Optional[str]
    aktif: bool
    class Config:
        from_attributes = True

@router.get("/stok", response_model=List[StokOut])
def list_stok(
    aktif_only: bool = True,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    q = db.query(StokKarti)
    if aktif_only:
        q = q.filter(StokKarti.aktif == True)
    return q.order_by(StokKarti.stok_kodu).all()

@router.post("/stok", response_model=StokOut)
def create_stok(
    body: StokCreate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    if db.query(StokKarti).filter(StokKarti.stok_kodu == body.stok_kodu).first():
        raise HTTPException(400, "Bu stok kodu zaten kayıtlı")
    stok = StokKarti(**body.model_dump())
    db.add(stok)
    db.commit()
    db.refresh(stok)
    return stok

@router.patch("/stok/{stok_id}", response_model=StokOut)
def update_stok(
    stok_id: int,
    body: StokUpdate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    stok = db.query(StokKarti).filter(StokKarti.id == stok_id).first()
    if not stok:
        raise HTTPException(404, "Stok kartı bulunamadı")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(stok, k, v)
    db.commit()
    db.refresh(stok)
    return stok


# ── CARİLER ────────────────────────────────────────────────

class CariCreate(BaseModel):
    cari_kodu: str
    unvan: str
    cari_tipi: str = "musteri"
    vergi_no: Optional[str] = None
    vergi_dairesi: Optional[str] = None
    telefon: Optional[str] = None
    adres: Optional[str] = None

class CariUpdate(BaseModel):
    unvan: Optional[str] = None
    cari_tipi: Optional[str] = None
    vergi_no: Optional[str] = None
    vergi_dairesi: Optional[str] = None
    telefon: Optional[str] = None
    adres: Optional[str] = None
    aktif: Optional[bool] = None

class CariOut(BaseModel):
    id: int
    cari_kodu: str
    unvan: str
    cari_tipi: str
    vergi_no: Optional[str]
    vergi_dairesi: Optional[str]
    telefon: Optional[str]
    adres: Optional[str]
    aktif: bool
    class Config:
        from_attributes = True

@router.get("/cari", response_model=List[CariOut])
def list_cari(
    aktif_only: bool = True,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    q = db.query(Cari)
    if aktif_only:
        q = q.filter(Cari.aktif == True)
    return q.order_by(Cari.cari_kodu).all()

@router.post("/cari", response_model=CariOut)
def create_cari(
    body: CariCreate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    if db.query(Cari).filter(Cari.cari_kodu == body.cari_kodu).first():
        raise HTTPException(400, "Bu cari kodu zaten kayıtlı")
    cari = Cari(**body.model_dump())
    db.add(cari)
    db.commit()
    db.refresh(cari)
    return cari

@router.patch("/cari/{cari_id}", response_model=CariOut)
def update_cari(
    cari_id: int,
    body: CariUpdate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    cari = db.query(Cari).filter(Cari.id == cari_id).first()
    if not cari:
        raise HTTPException(404, "Cari bulunamadı")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(cari, k, v)
    db.commit()
    db.refresh(cari)
    return cari


# ── OPERATÖRLER ────────────────────────────────────────────

class OperatorCreate(BaseModel):
    ad_soyad: str
    kullanici_adi: str
    sifre: str
    sicil_no: str
    departman: Optional[str] = None

class OperatorOut(BaseModel):
    id: int
    sicil_no: str
    departman: Optional[str]
    aktif: bool
    ad_soyad: str
    kullanici_adi: str
    class Config:
        from_attributes = True

@router.get("/operator", response_model=List[OperatorOut])
def list_operator(
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    operatorler = db.query(Operator).filter(Operator.aktif == True).all()
    result = []
    for op in operatorler:
        result.append(OperatorOut(
            id=op.id,
            sicil_no=op.sicil_no,
            departman=op.departman,
            aktif=op.aktif,
            ad_soyad=op.kullanici.ad_soyad,
            kullanici_adi=op.kullanici.kullanici_adi,
        ))
    return result

@router.post("/operator", response_model=OperatorOut)
def create_operator(
    body: OperatorCreate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_admin),
):
    from app.core.security import hash_password

    if db.query(Kullanici).filter(Kullanici.kullanici_adi == body.kullanici_adi).first():
        raise HTTPException(400, "Bu kullanıcı adı zaten alınmış")
    if db.query(Operator).filter(Operator.sicil_no == body.sicil_no).first():
        raise HTTPException(400, "Bu sicil numarası zaten kayıtlı")

    kullanici = Kullanici(
        ad_soyad=body.ad_soyad,
        kullanici_adi=body.kullanici_adi,
        sifre_hash=hash_password(body.sifre),
        rol="operator",
    )
    db.add(kullanici)
    db.flush()

    operator = Operator(
        kullanici_id=kullanici.id,
        sicil_no=body.sicil_no,
        departman=body.departman,
    )
    db.add(operator)
    db.commit()
    db.refresh(operator)

    return OperatorOut(
        id=operator.id,
        sicil_no=operator.sicil_no,
        departman=operator.departman,
        aktif=operator.aktif,
        ad_soyad=kullanici.ad_soyad,
        kullanici_adi=kullanici.kullanici_adi,
    )

@router.patch("/operator/{operator_id}/pasif")
def pasif_yap(
    operator_id: int,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_admin),
):
    op = db.query(Operator).filter(Operator.id == operator_id).first()
    if not op:
        raise HTTPException(404, "Operatör bulunamadı")
    op.aktif = False
    op.kullanici.aktif = False
    db.commit()
    return {"detail": "Operatör pasif yapıldı"}





class OperatorMakineYetkiUpdate(BaseModel):
    makine_ids: List[int]


class OperatorMakineYetkiOut(BaseModel):
    operator_id: int
    operator_adi: str
    sicil_no: str
    departman: Optional[str]
    makine_ids: List[int]


class MakineSecenekOut(BaseModel):
    id: int
    kod: str
    ad: str
    durum: str


class OperatorMakineYetkiListeOut(BaseModel):
    operatorler: List[OperatorMakineYetkiOut]
    makineler: List[MakineSecenekOut]


class TabletKayitUpdate(BaseModel):
    makine_id: Optional[int] = None
    tablet_adi: Optional[str] = None
    aktif: Optional[bool] = None


class TabletKayitOut(BaseModel):
    id: int
    tablet_id: str
    tablet_adi: Optional[str]
    makine_id: int
    makine_kodu: str
    makine_adi: str
    son_aktivite: Optional[datetime]
    aktif: bool
    olusturma_tarihi: datetime


@router.get("/operator-makine-yetkileri", response_model=OperatorMakineYetkiListeOut)
def list_operator_makine_yetkileri(
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    from app.models.models import Makine

    operatorler = db.query(Operator).filter(Operator.aktif == True).order_by(Operator.sicil_no).all()
    makineler = db.query(Makine).filter(Makine.aktif == True).order_by(Makine.kod).all()

    yetki_listesi = []
    for operator in operatorler:
        makine_ids = [
            kayit.makine_id
            for kayit in db.query(OperatorMakineYetki).filter(
                OperatorMakineYetki.operator_id == operator.id,
                OperatorMakineYetki.aktif == True,
            ).all()
        ]
        yetki_listesi.append(OperatorMakineYetkiOut(
            operator_id=operator.id,
            operator_adi=operator.kullanici.ad_soyad,
            sicil_no=operator.sicil_no,
            departman=operator.departman,
            makine_ids=makine_ids,
        ))

    return OperatorMakineYetkiListeOut(
        operatorler=yetki_listesi,
        makineler=[
            MakineSecenekOut(id=makine.id, kod=makine.kod, ad=makine.ad, durum=makine.durum)
            for makine in makineler
        ],
    )


@router.put("/operator/{operator_id}/makine-yetkileri", response_model=OperatorMakineYetkiOut)
def update_operator_makine_yetkileri(
    operator_id: int,
    body: OperatorMakineYetkiUpdate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    operator = db.query(Operator).filter(Operator.id == operator_id, Operator.aktif == True).first()
    if not operator:
        raise HTTPException(404, "Operatör bulunamadı")

    from app.models.models import Makine

    aktif_makineler = db.query(Makine.id).filter(Makine.aktif == True).all()
    aktif_makine_ids = {row[0] for row in aktif_makineler}
    gecersiz_ids = [makine_id for makine_id in body.makine_ids if makine_id not in aktif_makine_ids]
    if gecersiz_ids:
        raise HTTPException(400, "Geçersiz makine seçimi yapıldı")

    mevcut_kayitlar = db.query(OperatorMakineYetki).filter(
        OperatorMakineYetki.operator_id == operator_id,
    ).all()
    mevcut_map = {kayit.makine_id: kayit for kayit in mevcut_kayitlar}
    yeni_ids = set(body.makine_ids)

    for makine_id, kayit in mevcut_map.items():
        kayit.aktif = makine_id in yeni_ids

    for makine_id in yeni_ids:
        if makine_id not in mevcut_map:
            db.add(OperatorMakineYetki(
                operator_id=operator_id,
                makine_id=makine_id,
                aktif=True,
            ))

    db.commit()
    return OperatorMakineYetkiOut(
        operator_id=operator.id,
        operator_adi=operator.kullanici.ad_soyad,
        sicil_no=operator.sicil_no,
        departman=operator.departman,
        makine_ids=sorted(list(yeni_ids)),
    )


@router.get("/tablet-kayitlari", response_model=List[TabletKayitOut])
def list_tablet_kayitlari(
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    from app.models.models import Makine

    kayitlar = db.query(TabletKaydi, Makine).join(Makine, Makine.id == TabletKaydi.makine_id).order_by(
        TabletKaydi.aktif.desc(),
        TabletKaydi.son_aktivite.desc(),
        TabletKaydi.olusturma_tarihi.desc(),
    ).all()
    return [
        TabletKayitOut(
            id=tablet.id,
            tablet_id=tablet.tablet_id,
            tablet_adi=tablet.tablet_adi,
            makine_id=tablet.makine_id,
            makine_kodu=makine.kod,
            makine_adi=makine.ad,
            son_aktivite=tablet.son_aktivite,
            aktif=tablet.aktif,
            olusturma_tarihi=tablet.olusturma_tarihi,
        )
        for tablet, makine in kayitlar
    ]


@router.patch("/tablet-kayitlari/{tablet_kayit_id}", response_model=TabletKayitOut)
def update_tablet_kaydi(
    tablet_kayit_id: int,
    body: TabletKayitUpdate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    from app.models.models import Makine

    tablet = db.query(TabletKaydi).filter(TabletKaydi.id == tablet_kayit_id).first()
    if not tablet:
        raise HTTPException(404, "Tablet kaydı bulunamadı")

    hedef_makine_id = body.makine_id if body.makine_id is not None else tablet.makine_id
    makine = db.query(Makine).filter(Makine.id == hedef_makine_id, Makine.aktif == True).first()
    if not makine:
        raise HTTPException(404, "Makine bulunamadı")

    if body.makine_id is not None:
        cakisan = db.query(TabletKaydi).filter(
            TabletKaydi.makine_id == body.makine_id,
            TabletKaydi.aktif == True,
            TabletKaydi.id != tablet.id,
        ).first()
        if cakisan:
            raise HTTPException(400, "Bu makineye zaten başka bir tablet bağlı")
        tablet.makine_id = body.makine_id

    if body.tablet_adi is not None:
        tablet.tablet_adi = body.tablet_adi.strip() or None
    if body.aktif is not None:
        tablet.aktif = body.aktif

    db.commit()
    db.refresh(tablet)
    makine = db.query(Makine).filter(Makine.id == tablet.makine_id).first()
    return TabletKayitOut(
        id=tablet.id,
        tablet_id=tablet.tablet_id,
        tablet_adi=tablet.tablet_adi,
        makine_id=tablet.makine_id,
        makine_kodu=makine.kod if makine else "-",
        makine_adi=makine.ad if makine else "-",
        son_aktivite=tablet.son_aktivite,
        aktif=tablet.aktif,
        olusturma_tarihi=tablet.olusturma_tarihi,
    )


# ── ARIZALAR ───────────────────────────────────────────────

from app.models.models import Ariza
from datetime import datetime as dt

class ArizaOut(BaseModel):
    id: int
    makine_id: int
    makine_kodu: str
    makine_adi: str
    ariza_tipi: str
    aciklama: Optional[str]
    baslangic: datetime
    bitis: Optional[datetime]
    sure_dakika: Optional[int]
    durum: str
    cozum_aciklamasi: Optional[str]

class ArizaKapatRequest(BaseModel):
    cozum_aciklamasi: Optional[str] = None

@router.get("/ariza", response_model=List[ArizaOut])
def list_arizalar(
    durum: Optional[str] = None,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    from app.models.models import Makine
    q = db.query(Ariza, Makine).join(Makine, Makine.id == Ariza.makine_id)
    if durum:
        q = q.filter(Ariza.durum == durum)
    q = q.order_by(Ariza.baslangic.desc()).limit(200)
    result = []
    for ariza, makine in q.all():
        sure = None
        if ariza.bitis:
            sure = int((ariza.bitis - ariza.baslangic).total_seconds() / 60)
        result.append(ArizaOut(
            id=ariza.id,
            makine_id=ariza.makine_id,
            makine_kodu=makine.kod,
            makine_adi=makine.ad,
            ariza_tipi=ariza.ariza_tipi,
            aciklama=ariza.aciklama,
            baslangic=ariza.baslangic,
            bitis=ariza.bitis,
            sure_dakika=sure,
            durum=ariza.durum,
            cozum_aciklamasi=ariza.cozum_aciklamasi,
        ))
    return result

@router.patch("/ariza/{ariza_id}/kapat")
def ariza_kapat(
    ariza_id: int,
    body: ArizaKapatRequest,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    from app.models.models import Makine
    from app.services.makine_service import _redis_makine_guncelle
    ariza = db.query(Ariza).filter(Ariza.id == ariza_id).first()
    if not ariza:
        raise HTTPException(404, "Arıza bulunamadı")
    if ariza.durum == "giderildi":
        raise HTTPException(400, "Bu arıza zaten kapatılmış")
    now = dt.utcnow()
    ariza.durum = "giderildi"
    ariza.bitis = now
    ariza.cozum_aciklamasi = body.cozum_aciklamasi
    makine = db.query(Makine).filter(Makine.id == ariza.makine_id).first()
    if makine and makine.durum == "arizali":
        makine.durum = "bosta"
        makine.guncelleme_tarihi = now
    db.commit()
    _redis_makine_guncelle(db, ariza.makine_id)
    return {"detail": "Arıza kapatıldı"}


# ── KALİTE KONTROL ─────────────────────────────────────────

from app.models.models import KaliteKontrol, MakineIsEmri as MIE

class KaliteKontrolCreate(BaseModel):
    makine_is_emri_id: int
    uretilen_adet: int
    kabul_adet: int
    red_adet: int = 0
    fire_adet: int = 0
    ret_nedeni: Optional[str] = None
    aciklama: Optional[str] = None

class KaliteKontrolOut(BaseModel):
    id: int
    makine_is_emri_id: int
    makine_id: int
    operator_id: int
    kontrol_zamani: datetime
    uretilen_adet: int
    kabul_adet: int
    red_adet: int
    fire_adet: int
    ret_nedeni: Optional[str]
    aciklama: Optional[str]
    makine_kodu: str
    makine_adi: str
    operator_adi: str

class KaliteOzetOut(BaseModel):
    toplam_uretilen: int
    toplam_kabul: int
    toplam_red: int
    toplam_fire: int
    kalite_orani: float
    fire_orani: float

@router.post("/kalite", response_model=KaliteKontrolOut)
def kalite_kayit_ekle(
    body: KaliteKontrolCreate,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    from app.models.models import Makine
    mie = db.query(MIE).filter(MIE.id == body.makine_is_emri_id).first()
    if not mie:
        raise HTTPException(404, "İş emri bulunamadı")

    op = require_operator_machine_access(db, current_user.id, mie.makine_id)
    if mie.operator_id and mie.operator_id != op.id:
        raise HTTPException(403, "Bu is emri baska bir operator tarafindan sahiplenilmis")

    if body.kabul_adet + body.red_adet + body.fire_adet > body.uretilen_adet:
        raise HTTPException(400, "Kabul + Red + Fire toplamı üretilen adetten fazla olamaz")

    kk = KaliteKontrol(
        makine_is_emri_id=body.makine_is_emri_id,
        makine_id=mie.makine_id,
        operator_id=op.id,
        uretilen_adet=body.uretilen_adet,
        kabul_adet=body.kabul_adet,
        red_adet=body.red_adet,
        fire_adet=body.fire_adet,
        ret_nedeni=body.ret_nedeni,
        aciklama=body.aciklama,
    )
    db.add(kk)
    db.commit()
    db.refresh(kk)

    makine = db.query(Makine).filter(Makine.id == mie.makine_id).first()
    k = db.query(Kullanici).filter(Kullanici.id == current_user.id).first()

    return KaliteKontrolOut(
        id=kk.id,
        makine_is_emri_id=kk.makine_is_emri_id,
        makine_id=kk.makine_id,
        operator_id=kk.operator_id,
        kontrol_zamani=kk.kontrol_zamani,
        uretilen_adet=kk.uretilen_adet,
        kabul_adet=kk.kabul_adet,
        red_adet=kk.red_adet,
        fire_adet=kk.fire_adet,
        ret_nedeni=kk.ret_nedeni,
        aciklama=kk.aciklama,
        makine_kodu=makine.kod,
        makine_adi=makine.ad,
        operator_adi=k.ad_soyad,
    )

@router.get("/kalite", response_model=list[KaliteKontrolOut])
def list_kalite(
    makine_id: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    from app.models.models import Makine
    q = db.query(KaliteKontrol, Makine, Kullanici).join(
        Makine, Makine.id == KaliteKontrol.makine_id
    ).join(
        Operator, Operator.id == KaliteKontrol.operator_id
    ).join(
        Kullanici, Kullanici.id == Operator.kullanici_id
    )
    if makine_id:
        q = q.filter(KaliteKontrol.makine_id == makine_id)
    q = q.order_by(KaliteKontrol.kontrol_zamani.desc()).limit(limit)

    result = []
    for kk, makine, kullanici in q.all():
        result.append(KaliteKontrolOut(
            id=kk.id, makine_is_emri_id=kk.makine_is_emri_id,
            makine_id=kk.makine_id, operator_id=kk.operator_id,
            kontrol_zamani=kk.kontrol_zamani, uretilen_adet=kk.uretilen_adet,
            kabul_adet=kk.kabul_adet, red_adet=kk.red_adet,
            fire_adet=kk.fire_adet, ret_nedeni=kk.ret_nedeni,
            aciklama=kk.aciklama, makine_kodu=makine.kod,
            makine_adi=makine.ad, operator_adi=kullanici.ad_soyad,
        ))
    return result

@router.get("/kalite/ozet", response_model=KaliteOzetOut)
def kalite_ozet(
    makine_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    from sqlalchemy import func
    q = db.query(
        func.sum(KaliteKontrol.uretilen_adet),
        func.sum(KaliteKontrol.kabul_adet),
        func.sum(KaliteKontrol.red_adet),
        func.sum(KaliteKontrol.fire_adet),
    )
    if makine_id:
        q = q.filter(KaliteKontrol.makine_id == makine_id)
    row = q.first()
    uretilen = row[0] or 0
    kabul = row[1] or 0
    red = row[2] or 0
    fire = row[3] or 0
    kalite_orani = round((kabul / uretilen * 100), 1) if uretilen > 0 else 0.0
    fire_orani = round((fire / uretilen * 100), 1) if uretilen > 0 else 0.0
    return KaliteOzetOut(
        toplam_uretilen=uretilen, toplam_kabul=kabul,
        toplam_red=red, toplam_fire=fire,
        kalite_orani=kalite_orani, fire_orani=fire_orani,
    )


# ── BAKIM TAKVİMİ ──────────────────────────────────────────

from app.models.models import BakimPlani, BakimKaydi
from datetime import timedelta

class BakimPlaniCreate(BaseModel):
    makine_id: int
    bakim_adi: str
    bakim_tipi: str = "periyodik"
    peryot_gun: int = 30
    son_bakim_tarihi: Optional[datetime] = None
    sorumlu_id: Optional[int] = None
    aciklama: Optional[str] = None

class BakimPlaniOut(BaseModel):
    id: int
    makine_id: int
    makine_kodu: str
    makine_adi: str
    bakim_adi: str
    bakim_tipi: str
    peryot_gun: int
    son_bakim_tarihi: Optional[datetime]
    sonraki_bakim: Optional[datetime]
    sorumlu_adi: Optional[str]
    aciklama: Optional[str]
    aktif: bool
    gecikme_gun: Optional[int] = None
    durum: str = "normal"

class BakimKaydiCreate(BaseModel):
    bakim_plan_id: int
    notlar: Optional[str] = None

class BakimKaydiOut(BaseModel):
    id: int
    bakim_plan_id: int
    makine_id: int
    makine_kodu: str
    bakim_adi: str
    yapan_adi: str
    baslangic_zamani: datetime
    bitis_zamani: Optional[datetime]
    sure_dakika: Optional[int]
    notlar: Optional[str]
    durum: str

@router.get("/bakim/planlar", response_model=list[BakimPlaniOut])
def list_bakim_planlar(
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    from app.models.models import Makine
    planlar = db.query(BakimPlani).filter(BakimPlani.aktif == True).all()
    result = []
    now = datetime.utcnow()
    for p in planlar:
        makine = db.query(Makine).filter(Makine.id == p.makine_id).first()
        sorumlu_adi = None
        if p.sorumlu_id:
            op = db.query(Operator).filter(Operator.id == p.sorumlu_id).first()
            if op:
                k = db.query(Kullanici).filter(Kullanici.id == op.kullanici_id).first()
                sorumlu_adi = k.ad_soyad if k else None

        gecikme_gun = None
        durum = "normal"
        if p.sonraki_bakim:
            fark = (p.sonraki_bakim - now).days
            if fark < 0:
                gecikme_gun = abs(fark)
                durum = "gecikti"
            elif fark <= 7:
                durum = "yaklasıyor"

        result.append(BakimPlaniOut(
            id=p.id, makine_id=p.makine_id,
            makine_kodu=makine.kod if makine else "-",
            makine_adi=makine.ad if makine else "-",
            bakim_adi=p.bakim_adi, bakim_tipi=p.bakim_tipi,
            peryot_gun=p.peryot_gun,
            son_bakim_tarihi=p.son_bakim_tarihi,
            sonraki_bakim=p.sonraki_bakim,
            sorumlu_adi=sorumlu_adi,
            aciklama=p.aciklama, aktif=p.aktif,
            gecikme_gun=gecikme_gun, durum=durum,
        ))
    result.sort(key=lambda x: (0 if x.durum == "gecikti" else 1 if x.durum == "yaklasıyor" else 2))
    return result

@router.post("/bakim/planlar", response_model=BakimPlaniOut)
def create_bakim_plani(
    body: BakimPlaniCreate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    from app.models.models import Makine
    sonraki = None
    if body.son_bakim_tarihi:
        sonraki = body.son_bakim_tarihi + timedelta(days=body.peryot_gun)
    else:
        sonraki = datetime.utcnow() + timedelta(days=body.peryot_gun)

    plan = BakimPlani(
        makine_id=body.makine_id,
        bakim_adi=body.bakim_adi,
        bakim_tipi=body.bakim_tipi,
        peryot_gun=body.peryot_gun,
        son_bakim_tarihi=body.son_bakim_tarihi,
        sonraki_bakim=sonraki,
        sorumlu_id=body.sorumlu_id,
        aciklama=body.aciklama,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    makine = db.query(Makine).filter(Makine.id == plan.makine_id).first()
    return BakimPlaniOut(
        id=plan.id, makine_id=plan.makine_id,
        makine_kodu=makine.kod, makine_adi=makine.ad,
        bakim_adi=plan.bakim_adi, bakim_tipi=plan.bakim_tipi,
        peryot_gun=plan.peryot_gun,
        son_bakim_tarihi=plan.son_bakim_tarihi,
        sonraki_bakim=plan.sonraki_bakim,
        sorumlu_adi=None, aciklama=plan.aciklama, aktif=plan.aktif,
    )

@router.post("/bakim/kayit", response_model=BakimKaydiOut)
def bakim_kaydi_ekle(
    body: BakimKaydiCreate,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    from app.models.models import Makine
    plan = db.query(BakimPlani).filter(BakimPlani.id == body.bakim_plan_id).first()
    if not plan:
        raise HTTPException(404, "Bakım planı bulunamadı")

    op = db.query(Operator).filter(Operator.kullanici_id == current_user.id).first()
    if not op:
        raise HTTPException(403, "Operatör kaydı bulunamadı")

    now = datetime.utcnow()
    kayit = BakimKaydi(
        bakim_plan_id=plan.id,
        makine_id=plan.makine_id,
        yapan_id=op.id,
        baslangic_zamani=now,
        bitis_zamani=now,
        notlar=body.notlar,
        durum="tamamlandi",
    )
    db.add(kayit)

    plan.son_bakim_tarihi = now
    plan.sonraki_bakim = now + timedelta(days=plan.peryot_gun)

    db.commit()
    db.refresh(kayit)

    makine = db.query(Makine).filter(Makine.id == plan.makine_id).first()
    return BakimKaydiOut(
        id=kayit.id, bakim_plan_id=kayit.bakim_plan_id,
        makine_id=kayit.makine_id,
        makine_kodu=makine.kod if makine else "-",
        bakim_adi=plan.bakim_adi,
        yapan_adi=current_user.ad_soyad,
        baslangic_zamani=kayit.baslangic_zamani,
        bitis_zamani=kayit.bitis_zamani,
        sure_dakika=0,
        notlar=kayit.notlar,
        durum=kayit.durum,
    )

@router.get("/bakim/kayitlar", response_model=list[BakimKaydiOut])
def list_bakim_kayitlar(
    makine_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    from app.models.models import Makine
    q = db.query(BakimKaydi, BakimPlani, Makine).join(
        BakimPlani, BakimPlani.id == BakimKaydi.bakim_plan_id
    ).join(Makine, Makine.id == BakimKaydi.makine_id)
    if makine_id:
        q = q.filter(BakimKaydi.makine_id == makine_id)
    q = q.order_by(BakimKaydi.baslangic_zamani.desc()).limit(limit)

    result = []
    for kayit, plan, makine in q.all():
        op = db.query(Operator).filter(Operator.id == kayit.yapan_id).first()
        yapan_adi = "-"
        if op:
            k = db.query(Kullanici).filter(Kullanici.id == op.kullanici_id).first()
            yapan_adi = k.ad_soyad if k else "-"
        sure = None
        if kayit.bitis_zamani:
            sure = int((kayit.bitis_zamani - kayit.baslangic_zamani).total_seconds() / 60)
        result.append(BakimKaydiOut(
            id=kayit.id, bakim_plan_id=kayit.bakim_plan_id,
            makine_id=kayit.makine_id, makine_kodu=makine.kod,
            bakim_adi=plan.bakim_adi, yapan_adi=yapan_adi,
            baslangic_zamani=kayit.baslangic_zamani,
            bitis_zamani=kayit.bitis_zamani,
            sure_dakika=sure, notlar=kayit.notlar, durum=kayit.durum,
        ))
    return result


# ── TAKIM TALEPLERİ ────────────────────────────────────────

from app.models.models import TakimTalebi

class TalepCreate(BaseModel):
    makine_id: int
    talep_tipi: str
    aciklama: str
    oncelik: str = "normal"

class TalepCevapla(BaseModel):
    durum: str
    cevap_aciklamasi: Optional[str] = None

class TalepOut(BaseModel):
    id: int
    makine_id: int
    makine_kodu: str
    makine_adi: str
    operator_adi: str
    talep_tipi: str
    aciklama: str
    oncelik: str
    durum: str
    cevap_aciklamasi: Optional[str]
    cevap_zamani: Optional[datetime]
    olusturma_tarihi: datetime

@router.get("/talep", response_model=list[TalepOut])
def list_talepler(
    durum: Optional[str] = None,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    from app.models.models import Makine
    q = db.query(TakimTalebi, Makine, Operator, Kullanici).join(
        Makine, Makine.id == TakimTalebi.makine_id
    ).join(
        Operator, Operator.id == TakimTalebi.operator_id
    ).join(
        Kullanici, Kullanici.id == Operator.kullanici_id
    )
    if durum:
        q = q.filter(TakimTalebi.durum == durum)
    q = q.order_by(TakimTalebi.olusturma_tarihi.desc()).limit(200)

    result = []
    for talep, makine, op, kullanici in q.all():
        result.append(TalepOut(
            id=talep.id, makine_id=talep.makine_id,
            makine_kodu=makine.kod, makine_adi=makine.ad,
            operator_adi=kullanici.ad_soyad,
            talep_tipi=talep.talep_tipi,
            aciklama=talep.aciklama,
            oncelik=talep.oncelik,
            durum=talep.durum,
            cevap_aciklamasi=talep.cevap_aciklamasi,
            cevap_zamani=talep.cevap_zamani,
            olusturma_tarihi=talep.olusturma_tarihi,
        ))
    return result

@router.post("/talep", response_model=TalepOut)
def create_talep(
    body: TalepCreate,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    from app.models.models import Makine
    op = require_operator_machine_access(db, current_user.id, body.makine_id)
    makine = db.query(Makine).filter(Makine.id == body.makine_id, Makine.aktif == True).first()
    if not makine:
        raise HTTPException(404, "Makine bulunamadi")

    talep = TakimTalebi(
        makine_id=body.makine_id,
        operator_id=op.id,
        talep_tipi=body.talep_tipi,
        aciklama=body.aciklama,
        oncelik=body.oncelik,
    )
    db.add(talep)
    db.commit()
    db.refresh(talep)

    # Talep bildirimi gönder
    try:
        from app.services.bildirim_service import talep_bildirimi_gonder
        talep_bildirimi_gonder(
            makine_kodu=makine.kod,
            makine_adi=makine.ad,
            talep_tipi=talep.talep_tipi,
            aciklama=talep.aciklama,
            operator_adi=current_user.ad_soyad,
            oncelik=talep.oncelik,
        )
    except Exception:
        pass

    return TalepOut(
        id=talep.id, makine_id=talep.makine_id,
        makine_kodu=makine.kod, makine_adi=makine.ad,
        operator_adi=current_user.ad_soyad,
        talep_tipi=talep.talep_tipi,
        aciklama=talep.aciklama,
        oncelik=talep.oncelik,
        durum=talep.durum,
        cevap_aciklamasi=None,
        cevap_zamani=None,
        olusturma_tarihi=talep.olusturma_tarihi,
    )

@router.patch("/talep/{talep_id}/cevapla")
def talep_cevapla(
    talep_id: int,
    body: TalepCevapla,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(require_yonetici),
):
    talep = db.query(TakimTalebi).filter(TakimTalebi.id == talep_id).first()
    if not talep:
        raise HTTPException(404, "Talep bulunamadı")
    talep.durum = body.durum
    talep.cevap_aciklamasi = body.cevap_aciklamasi
    talep.cevap_veren_id = current_user.id
    talep.cevap_zamani = datetime.utcnow()
    db.commit()
    return {"detail": "Talep güncellendi"}


# ── AUDIT LOG ──────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id: int
    kullanici_id: Optional[int]
    kullanici_adi: Optional[str]
    rol: Optional[str]
    islem: str
    detay: Optional[str]
    ip_adresi: Optional[str]
    zaman: datetime
    basarili: bool

@router.get("/audit", response_model=list[AuditLogOut])
def list_audit(
    islem: Optional[str] = None,
    basarili: Optional[bool] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_admin),
):
    from sqlalchemy import text
    query = "SELECT TOP :limit Id, KullaniciId, KullaniciAdi, Rol, Islem, Detay, IpAdresi, Zaman, Basarili FROM AuditLog WHERE 1=1"
    params = {"limit": limit}
    if islem:
        query += " AND Islem = :islem"
        params["islem"] = islem
    if basarili is not None:
        query += " AND Basarili = :basarili"
        params["basarili"] = 1 if basarili else 0
    query += " ORDER BY Zaman DESC"

    rows = db.execute(text(query), params).fetchall()
    return [
        AuditLogOut(
            id=r[0], kullanici_id=r[1], kullanici_adi=r[2],
            rol=r[3], islem=r[4], detay=r[5], ip_adresi=r[6],
            zaman=r[7], basarili=bool(r[8]),
        )
        for r in rows
    ]


# ── ÜRETİM SAYACI ──────────────────────────────────────────

from app.models.models import UretimSayaci

class SayacKayitCreate(BaseModel):
    makine_is_emri_id: int
    uretilen_adet: int

class SayacKayitOut(BaseModel):
    id: int
    makine_is_emri_id: int
    uretilen_adet: int
    kayit_zamani: datetime
    toplam_uretilen: int
    oee_kullanilabilirlik: Optional[float]
    oee_performans: Optional[float]
    oee_kalite: Optional[float]
    oee: Optional[float]

@router.post("/sayac", response_model=SayacKayitOut)
def sayac_kayit(
    body: SayacKayitCreate,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    from app.models.models import Makine, MakineIsEmri as MIE2, KaliteKontrol
    from sqlalchemy import func

    mie = db.query(MIE2).filter(MIE2.id == body.makine_is_emri_id).first()
    if not mie:
        raise HTTPException(404, "İş emri bulunamadı")

    op = require_operator_machine_access(db, current_user.id, mie.makine_id)
    if mie.operator_id and mie.operator_id != op.id:
        raise HTTPException(403, "Bu is emri baska bir operator tarafindan sahiplenilmis")

    kayit = UretimSayaci(
        makine_is_emri_id=body.makine_is_emri_id,
        makine_id=mie.makine_id,
        operator_id=op.id,
        uretilen_adet=body.uretilen_adet,
    )
    db.add(kayit)
    db.commit()
    db.refresh(kayit)

    # Toplam üretilen
    toplam = db.query(func.sum(UretimSayaci.uretilen_adet)).filter(
        UretimSayaci.makine_is_emri_id == body.makine_is_emri_id
    ).scalar() or 0

    # OEE Hesaplama
    makine = db.query(Makine).filter(Makine.id == mie.makine_id).first()
    oee_k = oee_p = oee_kalite = oee = None

    if mie.baslangic_zamani:
        now = datetime.utcnow()
        toplam_sure_dk = (now - mie.baslangic_zamani).total_seconds() / 60

        # Duruş süresi
        from app.models.models import Ariza
        arizalar = db.query(Ariza).filter(
            Ariza.makine_id == mie.makine_id,
            Ariza.baslangic >= mie.baslangic_zamani,
        ).all()
        durus_dk = sum(
            (a.bitis - a.baslangic).total_seconds() / 60 if a.bitis
            else (now - a.baslangic).total_seconds() / 60
            for a in arizalar
        )

        # Kullanılabilirlik
        if toplam_sure_dk > 0:
            calisma_dk = toplam_sure_dk - durus_dk
            oee_k = round(max(0, min(100, (calisma_dk / toplam_sure_dk) * 100)), 1)

        # Performans (teorik süreye göre)
        if makine and makine.birim_sure_saniye and toplam_sure_dk > 0:
            teorik_adet = (toplam_sure_dk * 60) / makine.birim_sure_saniye
            if teorik_adet > 0:
                oee_p = round(min(100, (toplam / teorik_adet) * 100), 1)

        # Kalite (KaliteKontrol tablosundan)
        kk = db.query(
            func.sum(KaliteKontrol.uretilen_adet),
            func.sum(KaliteKontrol.kabul_adet)
        ).filter(KaliteKontrol.makine_is_emri_id == body.makine_is_emri_id).first()

        if kk and kk[0] and kk[0] > 0:
            oee_kalite = round((kk[1] / kk[0]) * 100, 1)
        else:
            oee_kalite = 100.0  # Kalite kaydı yoksa 100 kabul

        # OEE = K × P × Q
        if oee_k is not None and oee_p is not None:
            oee = round((oee_k / 100) * (oee_p / 100) * (oee_kalite / 100) * 100, 1)

    return SayacKayitOut(
        id=kayit.id,
        makine_is_emri_id=kayit.makine_is_emri_id,
        uretilen_adet=kayit.uretilen_adet,
        kayit_zamani=kayit.kayit_zamani,
        toplam_uretilen=toplam,
        oee_kullanilabilirlik=oee_k,
        oee_performans=oee_p,
        oee_kalite=oee_kalite,
        oee=oee,
    )

@router.get("/sayac/{makine_is_emri_id}")
def sayac_ozet(
    makine_is_emri_id: int,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    from sqlalchemy import func
    from app.models.models import IsEmri, MakineIsEmri as MIE3, Makine, Ariza, KaliteKontrol

    mie = db.query(MIE3).filter(MIE3.id == makine_is_emri_id).first()
    if not mie:
        raise HTTPException(404, "İş emri bulunamadı")

    toplam = db.query(func.sum(UretimSayaci.uretilen_adet)).filter(
        UretimSayaci.makine_is_emri_id == makine_is_emri_id
    ).scalar() or 0

    ie = db.query(IsEmri).filter(IsEmri.id == mie.is_emri_id).first()
    makine = db.query(Makine).filter(Makine.id == mie.makine_id).first()

    # OEE hesapla
    now = datetime.utcnow()
    oee_k = oee_p = oee_kalite = oee = None

    if mie.baslangic_zamani:
        toplam_sure_dk = (now - mie.baslangic_zamani).total_seconds() / 60
        arizalar = db.query(Ariza).filter(
            Ariza.makine_id == mie.makine_id,
            Ariza.baslangic >= mie.baslangic_zamani,
        ).all()
        durus_dk = sum(
            (a.bitis - a.baslangic).total_seconds() / 60 if a.bitis
            else (now - a.baslangic).total_seconds() / 60
            for a in arizalar
        )
        if toplam_sure_dk > 0:
            oee_k = round(max(0, min(100, ((toplam_sure_dk - durus_dk) / toplam_sure_dk) * 100)), 1)

        if makine and makine.birim_sure_saniye and toplam_sure_dk > 0:
            teorik = (toplam_sure_dk * 60) / makine.birim_sure_saniye
            if teorik > 0:
                oee_p = round(min(100, (toplam / teorik) * 100), 1)

        kk = db.query(
            func.sum(KaliteKontrol.uretilen_adet),
            func.sum(KaliteKontrol.kabul_adet)
        ).filter(KaliteKontrol.makine_is_emri_id == makine_is_emri_id).first()
        oee_kalite = round((kk[1] / kk[0]) * 100, 1) if kk and kk[0] else 100.0

        if oee_k is not None and oee_p is not None:
            oee = round((oee_k / 100) * (oee_p / 100) * (oee_kalite / 100) * 100, 1)

    return {
        "makine_is_emri_id": makine_is_emri_id,
        "is_emri_no": ie.is_emri_no if ie else "-",
        "hedef_adet": ie.miktar if ie else 0,
        "toplam_uretilen": toplam,
        "kalan_adet": max(0, (ie.miktar if ie else 0) - toplam),
        "tamamlanma_yuzdesi": round((toplam / ie.miktar * 100), 1) if ie and ie.miktar > 0 else 0,
        "birim_sure_saniye": makine.birim_sure_saniye if makine else None,
        "oee_kullanilabilirlik": oee_k,
        "oee_performans": oee_p,
        "oee_kalite": oee_kalite,
        "oee": oee,
    }


# ── ÜRETİM PARTİLERİ & QR ─────────────────────────────────

from app.models.models import UretimPartisi, StokKarti
import qrcode
import json
from io import BytesIO
from fastapi.responses import StreamingResponse as SR2
from sqlalchemy.orm import aliased
Kullanici2 = aliased(Kullanici)

class PartiOut(BaseModel):
    id: int
    parti_kodu: str
    is_emri_no: str
    makine_id: int
    stok_adi: str
    uretilen_adet: int
    kabul_adet: int
    fire_adet: int
    baslangic_zamani: datetime
    bitis_zamani: datetime
    operator_adi: str
    qr_icerik: str

@router.get("/parti", response_model=list[PartiOut])
def list_partiler(
    stok_id: Optional[int] = None,
    makine_id: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    from app.models.models import Makine
    q = db.query(UretimPartisi, Makine, StokKarti, Operator, Kullanici2).join(
        Makine, Makine.id == UretimPartisi.makine_id
    ).join(
        StokKarti, StokKarti.id == UretimPartisi.stok_id
    ).join(
        Operator, Operator.id == UretimPartisi.operator_id
    ).join(
        Kullanici2, Kullanici2.id == Operator.kullanici_id
    )
    if stok_id:
        q = q.filter(UretimPartisi.stok_id == stok_id)
    if makine_id:
        q = q.filter(UretimPartisi.makine_id == makine_id)
    q = q.order_by(UretimPartisi.olusturma_tarihi.desc()).limit(limit)

    result = []
    for parti, makine, stok, op, k in q.all():
        result.append(PartiOut(
            id=parti.id, parti_kodu=parti.parti_kodu,
            is_emri_no=parti.is_emri_no, makine_id=parti.makine_id,
            stok_adi=stok.stok_adi, uretilen_adet=parti.uretilen_adet,
            kabul_adet=parti.kabul_adet, fire_adet=parti.fire_adet,
            baslangic_zamani=parti.baslangic_zamani, bitis_zamani=parti.bitis_zamani,
            operator_adi=k.ad_soyad, qr_icerik=parti.qr_icerik,
        ))
    return result

@router.get("/parti/sorgula/{parti_kodu}")
def parti_sorgula(
    parti_kodu: str,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    from app.models.models import Makine
    parti = db.query(UretimPartisi).filter(UretimPartisi.parti_kodu == parti_kodu).first()
    if not parti:
        raise HTTPException(404, "Parti bulunamadı")

    makine = db.query(Makine).filter(Makine.id == parti.makine_id).first()
    stok = db.query(StokKarti).filter(StokKarti.id == parti.stok_id).first()
    op = db.query(Operator).filter(Operator.id == parti.operator_id).first()
    k = db.query(Kullanici).filter(Kullanici.id == op.kullanici_id).first() if op else None

    sure_dk = int((parti.bitis_zamani - parti.baslangic_zamani).total_seconds() / 60)

    return {
        "parti_kodu": parti.parti_kodu,
        "is_emri_no": parti.is_emri_no,
        "urun": stok.stok_adi if stok else "-",
        "stok_kodu": stok.stok_kodu if stok else "-",
        "makine": f"{makine.kod} — {makine.ad}" if makine else "-",
        "operator": k.ad_soyad if k else "-",
        "uretilen_adet": parti.uretilen_adet,
        "kabul_adet": parti.kabul_adet,
        "fire_adet": parti.fire_adet,
        "kalite_orani": round((parti.kabul_adet / parti.uretilen_adet * 100), 1) if parti.uretilen_adet > 0 else 0,
        "baslangic": parti.baslangic_zamani.strftime("%d.%m.%Y %H:%M"),
        "bitis": parti.bitis_zamani.strftime("%d.%m.%Y %H:%M"),
        "sure": f"{sure_dk // 60}s {sure_dk % 60}dk" if sure_dk >= 60 else f"{sure_dk}dk",
    }

@router.get("/parti/{parti_id}/qr")
def parti_qr_indir(
    parti_id: int,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    if token:
        from app.core.security import decode_token
        try:
            decode_token(token)
        except Exception:
            raise HTTPException(401, "Geçersiz token")

    parti = db.query(UretimPartisi).filter(UretimPartisi.id == parti_id).first()
    if not parti:
        raise HTTPException(404, "Parti bulunamadı")

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(parti.parti_kodu)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return SR2(
        buf,
        media_type="image/png",
        headers={
            "Content-Disposition": f"attachment; filename=qr_{parti.parti_kodu}.png",
            "Access-Control-Allow-Origin": "*",
        }
    )

class OperatorSifreDegistir(BaseModel):
    yeni_sifre: str

@router.patch("/operator/{operator_id}/sifre")
def operator_sifre_degistir(
    operator_id: int,
    body: OperatorSifreDegistir,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_admin),
):
    from app.core.security import hash_password
    op = db.query(Operator).filter(Operator.id == operator_id).first()
    if not op:
        raise HTTPException(404, "Operatör bulunamadı")
    op.kullanici.sifre_hash = hash_password(body.yeni_sifre)
    db.commit()
    return {"detail": "Şifre güncellendi"}