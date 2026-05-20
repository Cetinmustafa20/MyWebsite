from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel
from app.db.database import get_db
from app.models.models import Kullanici
from app.core.security import get_current_user, require_admin

router = APIRouter(prefix="/fire", tags=["fire"])


class FireKayitCreate(BaseModel):
    makine_is_emri_id: int
    giris_agirligi: float
    cikis_agirligi: float
    aciklama: Optional[str] = None

class FireKayitOut(BaseModel):
    id: int
    makine_is_emri_id: int
    is_emri_no: Optional[str]
    stok_adi: Optional[str]
    makine_kodu: Optional[str]
    operator_adi: Optional[str]
    giris_agirligi: float
    cikis_agirligi: float
    fire_miktari: float
    fire_yuzdesi: float
    olusturma_tarihi: datetime

class FireOzetOut(BaseModel):
    toplam_giris: float
    toplam_fire: float
    ort_fire_yuzdesi: float
    en_cok_fire_makine: Optional[str]
    en_cok_fire_urun: Optional[str]

class StokAgirlikUpdate(BaseModel):
    teorik_agirlik: Optional[float]


@router.patch("/stok/{stok_id}/agirlik")
def stok_agirlik_guncelle(
    stok_id: int,
    body: StokAgirlikUpdate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_admin),
):
    sonuc = db.execute(text("UPDATE StokKartlari SET TeorikAgirlik = :agirlik WHERE Id = :id"),
                       {"agirlik": body.teorik_agirlik, "id": stok_id})
    db.commit()
    if sonuc.rowcount == 0:
        raise HTTPException(404, "Stok bulunamadi")
    return {"detail": "Agirlik guncellendi"}


@router.get("/stok/{stok_id}/agirlik")
def stok_agirlik_getir(
    stok_id: int,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    row = db.execute(text("SELECT TeorikAgirlik FROM StokKartlari WHERE Id = :id"),
                     {"id": stok_id}).fetchone()
    if not row:
        raise HTTPException(404, "Stok bulunamadi")
    return {"teorik_agirlik": float(row[0]) if row[0] else None}


@router.post("/kayit", response_model=FireKayitOut)
def fire_kayit_olustur(
    body: FireKayitCreate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    if body.cikis_agirligi > body.giris_agirligi:
        raise HTTPException(400, "Cikis agirlik giris agirliktan buyuk olamaz")
    if body.giris_agirligi <= 0:
        raise HTTPException(400, "Giris agirlik 0dan buyuk olmali")

    fire_miktari = round(body.giris_agirligi - body.cikis_agirligi, 3)
    fire_yuzdesi = round((fire_miktari / body.giris_agirligi) * 100, 2)

    mie = db.execute(text("""
        SELECT ie.IsEmriNo, s.StokAdi, m.Kod, k.AdSoyad
        FROM MakineIsEmirleri mie
        JOIN IsEmirleri ie ON ie.Id = mie.IsEmriId
        JOIN StokKartlari s ON s.Id = ie.StokId
        JOIN Makineler m ON m.Id = mie.MakineId
        LEFT JOIN Operatorler o ON o.Id = mie.OperatorId
        LEFT JOIN Kullanicilar k ON k.Id = o.KullaniciId
        WHERE mie.Id = :id
    """), {"id": body.makine_is_emri_id}).fetchone()

    mevcut = db.execute(text("SELECT Id FROM FireKayitlari WHERE MakineIsEmriId = :id"),
                        {"id": body.makine_is_emri_id}).fetchone()

    if mevcut:
        db.execute(text("""
            UPDATE FireKayitlari SET
                GirisAgirligi = :giris, CikisAgirligi = :cikis,
                FireMiktari = :fire, FireYuzdesi = :yuzde,
                OlusturmaTarihi = :tarih
            WHERE MakineIsEmriId = :mie_id
        """), {
            "giris": body.giris_agirligi, "cikis": body.cikis_agirligi,
            "fire": fire_miktari, "yuzde": fire_yuzdesi,
            "tarih": datetime.now(), "mie_id": body.makine_is_emri_id,
        })
        kayit_id = mevcut[0]
    else:
        kayit_id = db.execute(text("""
            INSERT INTO FireKayitlari
                (MakineIsEmriId, GirisAgirligi, CikisAgirligi,
                 FireMiktari, FireYuzdesi, OlusturmaTarihi)
            OUTPUT INSERTED.Id
            VALUES (:mie_id, :giris, :cikis, :fire, :yuzde, :tarih)
        """), {
            "mie_id": body.makine_is_emri_id,
            "giris": body.giris_agirligi, "cikis": body.cikis_agirligi,
            "fire": fire_miktari, "yuzde": fire_yuzdesi,
            "tarih": datetime.now(),
        }).scalar()

    db.commit()

    return FireKayitOut(
        id=kayit_id, makine_is_emri_id=body.makine_is_emri_id,
        is_emri_no=mie[0] if mie else None,
        stok_adi=mie[1] if mie else None,
        makine_kodu=mie[2] if mie else None,
        operator_adi=mie[3] if mie else None,
        giris_agirligi=body.giris_agirligi,
        cikis_agirligi=body.cikis_agirligi,
        fire_miktari=fire_miktari,
        fire_yuzdesi=fire_yuzdesi,
        olusturma_tarihi=datetime.now(),
    )


@router.get("/kayit/{makine_is_emri_id}")
def fire_kayit_getir(
    makine_is_emri_id: int,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    row = db.execute(text("""
        SELECT fk.Id, fk.MakineIsEmriId,
               fk.GirisAgirligi, fk.CikisAgirligi,
               fk.FireMiktari, fk.FireYuzdesi, fk.OlusturmaTarihi
        FROM FireKayitlari fk WHERE fk.MakineIsEmriId = :id
    """), {"id": makine_is_emri_id}).fetchone()
    if not row:
        return None
    mie = db.execute(text("""
        SELECT ie.IsEmriNo, s.StokAdi, m.Kod, k.AdSoyad
        FROM MakineIsEmirleri mie
        JOIN IsEmirleri ie ON ie.Id = mie.IsEmriId
        JOIN StokKartlari s ON s.Id = ie.StokId
        JOIN Makineler m ON m.Id = mie.MakineId
        LEFT JOIN Operatorler o ON o.Id = mie.OperatorId
        LEFT JOIN Kullanicilar k ON k.Id = o.KullaniciId
        WHERE mie.Id = :id
    """), {"id": makine_is_emri_id}).fetchone()
    return FireKayitOut(
        id=row[0], makine_is_emri_id=row[1],
        is_emri_no=mie[0] if mie else None, stok_adi=mie[1] if mie else None,
        makine_kodu=mie[2] if mie else None, operator_adi=mie[3] if mie else None,
        giris_agirligi=float(row[2]), cikis_agirligi=float(row[3]),
        fire_miktari=float(row[4]), fire_yuzdesi=float(row[5]),
        olusturma_tarihi=row[6],
    )


@router.get("/liste", response_model=List[FireKayitOut])
def fire_liste(
    baslangic: Optional[date] = None,
    bitis: Optional[date] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    where = "WHERE 1=1"
    params = {"limit": limit}
    if baslangic:
        where += " AND fk.OlusturmaTarihi >= :bas"
        params["bas"] = datetime.combine(baslangic, datetime.min.time())
    if bitis:
        where += " AND fk.OlusturmaTarihi <= :bit"
        params["bit"] = datetime.combine(bitis, datetime.max.time())

    rows = db.execute(text(f"""
        SELECT TOP (:limit)
               fk.Id, fk.MakineIsEmriId,
               ie.IsEmriNo, s.StokAdi, m.Kod, k.AdSoyad,
               fk.GirisAgirligi, fk.CikisAgirligi,
               fk.FireMiktari, fk.FireYuzdesi, fk.OlusturmaTarihi
        FROM FireKayitlari fk
        JOIN MakineIsEmirleri mie ON mie.Id = fk.MakineIsEmriId
        JOIN IsEmirleri ie ON ie.Id = mie.IsEmriId
        JOIN StokKartlari s ON s.Id = ie.StokId
        JOIN Makineler m ON m.Id = mie.MakineId
        LEFT JOIN Operatorler o ON o.Id = mie.OperatorId
        LEFT JOIN Kullanicilar k ON k.Id = o.KullaniciId
        {where}
        ORDER BY fk.OlusturmaTarihi DESC
    """), params).fetchall()

    return [FireKayitOut(
        id=r[0], makine_is_emri_id=r[1],
        is_emri_no=r[2], stok_adi=r[3], makine_kodu=r[4], operator_adi=r[5],
        giris_agirligi=float(r[6]), cikis_agirligi=float(r[7]),
        fire_miktari=float(r[8]), fire_yuzdesi=float(r[9]),
        olusturma_tarihi=r[10],
    ) for r in rows]


@router.get("/ozet", response_model=FireOzetOut)
def fire_ozet(
    baslangic: Optional[date] = None,
    bitis: Optional[date] = None,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    where = "WHERE 1=1"
    params = {}
    if baslangic:
        where += " AND fk.OlusturmaTarihi >= :bas"
        params["bas"] = datetime.combine(baslangic, datetime.min.time())
    if bitis:
        where += " AND fk.OlusturmaTarihi <= :bit"
        params["bit"] = datetime.combine(bitis, datetime.max.time())

    ozet = db.execute(text(f"""
        SELECT SUM(fk.GirisAgirligi), SUM(fk.FireMiktari), AVG(fk.FireYuzdesi)
        FROM FireKayitlari fk {where}
    """), params).fetchone()

    makine = db.execute(text(f"""
        SELECT TOP 1 m.Kod + ' - ' + m.Ad
        FROM FireKayitlari fk
        JOIN MakineIsEmirleri mie ON mie.Id = fk.MakineIsEmriId
        JOIN Makineler m ON m.Id = mie.MakineId
        {where}
        GROUP BY mie.MakineId, m.Kod, m.Ad
        ORDER BY SUM(fk.FireMiktari) DESC
    """), params).scalar()

    urun = db.execute(text(f"""
        SELECT TOP 1 s.StokAdi
        FROM FireKayitlari fk
        JOIN MakineIsEmirleri mie ON mie.Id = fk.MakineIsEmriId
        JOIN IsEmirleri ie ON ie.Id = mie.IsEmriId
        JOIN StokKartlari s ON s.Id = ie.StokId
        {where}
        GROUP BY ie.StokId, s.StokAdi
        ORDER BY SUM(fk.FireMiktari) DESC
    """), params).scalar()

    return FireOzetOut(
        toplam_giris=float(ozet[0] or 0),
        toplam_fire=float(ozet[1] or 0),
        ort_fire_yuzdesi=float(ozet[2] or 0),
        en_cok_fire_makine=makine,
        en_cok_fire_urun=urun,
    )