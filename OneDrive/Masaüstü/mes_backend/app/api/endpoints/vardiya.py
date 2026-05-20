"""
Vardiya Yönetimi Endpoint'leri
- Vardiya tanımları CRUD (admin saatleri ayarlar)
- Operatör vardiya planı
- İzin talepleri ve onay akışı
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import date, datetime, timedelta
from pydantic import BaseModel
from app.db.database import get_db
from app.models.models import Kullanici
from app.core.security import get_current_user, require_yonetici

router = APIRouter(prefix="/vardiya", tags=["vardiya"])


# ── PYDANTIC ────────────────────────────────────────────────

class VardiyaCreate(BaseModel):
    ad: str
    baslangic_saati: str   # "06:00"
    bitis_saati: str       # "14:00"
    renk: Optional[str] = "#3b82f6"

class VardiyaOut(BaseModel):
    id: int
    ad: str
    baslangic_saati: str
    bitis_saati: str
    renk: Optional[str]
    aktif: bool

class VardiyaPlanCreate(BaseModel):
    operator_id: int
    vardiya_id: int
    tarih: date
    notlar: Optional[str] = None

class VardiyaPlanTopluCreate(BaseModel):
    operator_idler: List[int]
    vardiya_id: int
    baslangic_tarihi: date
    bitis_tarihi: date
    notlar: Optional[str] = None

class VardiyaPlanOut(BaseModel):
    id: int
    operator_id: int
    ad_soyad: str
    sicil_no: str
    vardiya_id: int
    vardiya_adi: str
    vardiya_renk: Optional[str]
    baslangic_saati: str
    bitis_saati: str
    tarih: date
    notlar: Optional[str]

class IzinTalebiCreate(BaseModel):
    operator_id: int
    izin_tipi: str   # yillik | hastalik | mazeret | ucretsiz
    baslangic_tarihi: date
    bitis_tarihi: date
    aciklama: Optional[str] = None

class IzinOnayCreate(BaseModel):
    red_nedeni: Optional[str] = None

class IzinTalebiOut(BaseModel):
    id: int
    operator_id: int
    ad_soyad: str
    sicil_no: str
    izin_tipi: str
    baslangic_tarihi: date
    bitis_tarihi: date
    gun_sayisi: int
    aciklama: Optional[str]
    durum: str
    onaylayan: Optional[str]
    onay_tarihi: Optional[datetime]
    red_nedeni: Optional[str]
    olusturma_tarihi: datetime

class BugunVardiyaOut(BaseModel):
    vardiya_id: int
    vardiya_adi: str
    vardiya_renk: Optional[str]
    baslangic_saati: str
    bitis_saati: str
    operator_sayisi: int
    operatorler: List[dict]


# ── VARDİYA TANIM CRUD ──────────────────────────────────────

@router.get("/tanimlar", response_model=List[VardiyaOut])
def vardiya_listele(
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    rows = db.execute(text("""
        SELECT Id, Ad, CONVERT(VARCHAR(5), BaslangicSaati, 108),
               CONVERT(VARCHAR(5), BitisSaati, 108), Renk, Aktif
        FROM VardiyaTanimlari
        ORDER BY BaslangicSaati
    """)).fetchall()
    return [VardiyaOut(id=r[0], ad=r[1], baslangic_saati=r[2],
                       bitis_saati=r[3], renk=r[4], aktif=bool(r[5]))
            for r in rows]


@router.post("/tanimlar", response_model=VardiyaOut)
def vardiya_ekle(
    body: VardiyaCreate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    row = db.execute(text("""
        INSERT INTO VardiyaTanimlari (Ad, BaslangicSaati, BitisSaati, Renk)
        OUTPUT INSERTED.Id, INSERTED.Ad,
               CONVERT(VARCHAR(5), INSERTED.BaslangicSaati, 108),
               CONVERT(VARCHAR(5), INSERTED.BitisSaati, 108),
               INSERTED.Renk, INSERTED.Aktif
        VALUES (:ad, :bas, :bit, :renk)
    """), {"ad": body.ad, "bas": body.baslangic_saati,
           "bit": body.bitis_saati, "renk": body.renk}).fetchone()
    db.commit()
    return VardiyaOut(id=row[0], ad=row[1], baslangic_saati=row[2],
                      bitis_saati=row[3], renk=row[4], aktif=bool(row[5]))


@router.patch("/tanimlar/{vardiya_id}", response_model=VardiyaOut)
def vardiya_guncelle(
    vardiya_id: int,
    body: VardiyaCreate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    row = db.execute(text("""
        UPDATE VardiyaTanimlari
        SET Ad=:ad, BaslangicSaati=:bas, BitisSaati=:bit, Renk=:renk
        OUTPUT INSERTED.Id, INSERTED.Ad,
               CONVERT(VARCHAR(5), INSERTED.BaslangicSaati, 108),
               CONVERT(VARCHAR(5), INSERTED.BitisSaati, 108),
               INSERTED.Renk, INSERTED.Aktif
        WHERE Id=:id
    """), {"ad": body.ad, "bas": body.baslangic_saati,
           "bit": body.bitis_saati, "renk": body.renk, "id": vardiya_id}).fetchone()
    if not row:
        raise HTTPException(404, "Vardiya bulunamadı")
    db.commit()
    return VardiyaOut(id=row[0], ad=row[1], baslangic_saati=row[2],
                      bitis_saati=row[3], renk=row[4], aktif=bool(row[5]))


@router.delete("/tanimlar/{vardiya_id}")
def vardiya_sil(
    vardiya_id: int,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    db.execute(text("UPDATE VardiyaTanimlari SET Aktif=0 WHERE Id=:id"), {"id": vardiya_id})
    db.commit()
    return {"detail": "Vardiya silindi"}


# ── VARDİYA PLANI ────────────────────────────────────────────

@router.get("/plan", response_model=List[VardiyaPlanOut])
def vardiya_plan_listele(
    baslangic: date = Query(default=None),
    bitis: date = Query(default=None),
    operator_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    if not baslangic:
        baslangic = date.today()
    if not bitis:
        bitis = baslangic + timedelta(days=6)

    where = "WHERE vp.Tarih BETWEEN :bas AND :bit"
    params = {"bas": baslangic, "bit": bitis}
    if operator_id:
        where += " AND vp.OperatorId = :oid"
        params["oid"] = operator_id

    rows = db.execute(text(f"""
        SELECT vp.Id, vp.OperatorId, k.AdSoyad, o.SicilNo,
               vp.VardiyaId, vt.Ad,
               ISNULL(vt.Renk, '#3b82f6'),
               CONVERT(VARCHAR(5), vt.BaslangicSaati, 108),
               CONVERT(VARCHAR(5), vt.BitisSaati, 108),
               vp.Tarih, vp.Notlar
        FROM VardiyaPlani vp
        JOIN Operatorler o ON o.Id = vp.OperatorId
        JOIN Kullanicilar k ON k.Id = o.KullaniciId
        JOIN VardiyaTanimlari vt ON vt.Id = vp.VardiyaId
        {where}
        ORDER BY vp.Tarih, vt.BaslangicSaati, k.AdSoyad
    """), params).fetchall()

    return [VardiyaPlanOut(
        id=r[0], operator_id=r[1], ad_soyad=r[2], sicil_no=r[3],
        vardiya_id=r[4], vardiya_adi=r[5], vardiya_renk=r[6],
        baslangic_saati=r[7], bitis_saati=r[8],
        tarih=r[9], notlar=r[10],
    ) for r in rows]


@router.post("/plan", response_model=dict)
def vardiya_plan_ekle(
    body: VardiyaPlanCreate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    # Çakışma kontrolü
    mevcut = db.execute(text("""
        SELECT Id FROM VardiyaPlani
        WHERE OperatorId=:oid AND Tarih=:tarih
    """), {"oid": body.operator_id, "tarih": body.tarih}).fetchone()

    if mevcut:
        # Güncelle
        db.execute(text("""
            UPDATE VardiyaPlani SET VardiyaId=:vid, Notlar=:n
            WHERE OperatorId=:oid AND Tarih=:tarih
        """), {"vid": body.vardiya_id, "n": body.notlar,
               "oid": body.operator_id, "tarih": body.tarih})
    else:
        db.execute(text("""
            INSERT INTO VardiyaPlani (OperatorId, VardiyaId, Tarih, Notlar)
            VALUES (:oid, :vid, :tarih, :n)
        """), {"oid": body.operator_id, "vid": body.vardiya_id,
               "tarih": body.tarih, "n": body.notlar})
    db.commit()
    return {"detail": "Vardiya planı kaydedildi"}


@router.post("/plan/toplu", response_model=dict)
def vardiya_plan_toplu_ekle(
    body: VardiyaPlanTopluCreate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    """Birden fazla operatöre, tarih aralığında toplu vardiya ata."""
    gun = body.baslangic_tarihi
    eklenen = 0
    while gun <= body.bitis_tarihi:
        for op_id in body.operator_idler:
            mevcut = db.execute(text("""
                SELECT Id FROM VardiyaPlani WHERE OperatorId=:oid AND Tarih=:t
            """), {"oid": op_id, "t": gun}).fetchone()
            if mevcut:
                db.execute(text("""
                    UPDATE VardiyaPlani SET VardiyaId=:vid WHERE OperatorId=:oid AND Tarih=:t
                """), {"vid": body.vardiya_id, "oid": op_id, "t": gun})
            else:
                db.execute(text("""
                    INSERT INTO VardiyaPlani (OperatorId, VardiyaId, Tarih, Notlar)
                    VALUES (:oid, :vid, :t, :n)
                """), {"oid": op_id, "vid": body.vardiya_id, "t": gun, "n": body.notlar})
            eklenen += 1
        gun += timedelta(days=1)
    db.commit()
    return {"detail": f"{eklenen} vardiya planı kaydedildi"}


@router.delete("/plan/{plan_id}")
def vardiya_plan_sil(
    plan_id: int,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    db.execute(text("DELETE FROM VardiyaPlani WHERE Id=:id"), {"id": plan_id})
    db.commit()
    return {"detail": "Vardiya planı silindi"}


@router.get("/bugun", response_model=List[BugunVardiyaOut])
def bugun_vardiyalar(
    tarih: Optional[date] = None,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    """Bugün hangi vardiyada kim var."""
    hedef = tarih or date.today()

    vardiyalar = db.execute(text("""
        SELECT DISTINCT vt.Id, vt.Ad, vt.Renk,
               CONVERT(VARCHAR(5), vt.BaslangicSaati, 108),
               CONVERT(VARCHAR(5), vt.BitisSaati, 108),
               vt.BaslangicSaati AS SortKey
        FROM VardiyaPlani vp
        JOIN VardiyaTanimlari vt ON vt.Id = vp.VardiyaId
        WHERE vp.Tarih = :tarih
        ORDER BY vt.BaslangicSaati
    """), {"tarih": hedef}).fetchall()

    result = []
    for v in vardiyalar:
        ops = db.execute(text("""
            SELECT k.AdSoyad, o.SicilNo, o.Departman
            FROM VardiyaPlani vp
            JOIN Operatorler o ON o.Id = vp.OperatorId
            JOIN Kullanicilar k ON k.Id = o.KullaniciId
            WHERE vp.VardiyaId = :vid AND vp.Tarih = :tarih
            ORDER BY k.AdSoyad
        """), {"vid": v[0], "tarih": hedef}).fetchall()

        result.append(BugunVardiyaOut(
            vardiya_id=v[0], vardiya_adi=v[1], vardiya_renk=v[2],
            baslangic_saati=v[3], bitis_saati=v[4],
            operator_sayisi=len(ops),
            operatorler=[{"ad_soyad": o[0], "sicil_no": o[1], "departman": o[2]} for o in ops],
        ))
    return result


# ── İZİN TALEPLERİ ───────────────────────────────────────────

@router.get("/izin", response_model=List[IzinTalebiOut])
def izin_listele(
    durum: Optional[str] = None,
    operator_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    where = "WHERE 1=1"
    params = {}
    if durum:
        where += " AND it.Durum=:durum"
        params["durum"] = durum
    if operator_id:
        where += " AND it.OperatorId=:oid"
        params["oid"] = operator_id

    rows = db.execute(text(f"""
        SELECT it.Id, it.OperatorId, k.AdSoyad, o.SicilNo,
               it.IzinTipi, it.BaslangicTarihi, it.BitisTarihi,
               it.GunSayisi, it.Aciklama, it.Durum,
               onk.AdSoyad, it.OnayTarihi, it.RedNedeni, it.OlusturmaTarihi
        FROM IzinTalepleri it
        JOIN Operatorler o ON o.Id = it.OperatorId
        JOIN Kullanicilar k ON k.Id = o.KullaniciId
        LEFT JOIN Kullanicilar onk ON onk.Id = it.OnaylayanId
        {where}
        ORDER BY it.OlusturmaTarihi DESC
    """), params).fetchall()

    return [IzinTalebiOut(
        id=r[0], operator_id=r[1], ad_soyad=r[2], sicil_no=r[3],
        izin_tipi=r[4], baslangic_tarihi=r[5], bitis_tarihi=r[6],
        gun_sayisi=int(r[7] or 0), aciklama=r[8], durum=r[9],
        onaylayan=r[10], onay_tarihi=r[11], red_nedeni=r[12],
        olusturma_tarihi=r[13],
    ) for r in rows]


@router.post("/izin", response_model=dict)
def izin_talebi_olustur(
    body: IzinTalebiCreate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    gecerli_tipler = ["yillik", "hastalik", "mazeret", "ucretsiz"]
    if body.izin_tipi not in gecerli_tipler:
        raise HTTPException(400, f"Geçersiz izin tipi. Geçerli: {gecerli_tipler}")
    if body.bitis_tarihi < body.baslangic_tarihi:
        raise HTTPException(400, "Bitiş tarihi başlangıç tarihinden önce olamaz")

    db.execute(text("""
        INSERT INTO IzinTalepleri
            (OperatorId, IzinTipi, BaslangicTarihi, BitisTarihi, Aciklama)
        VALUES (:oid, :tip, :bas, :bit, :ac)
    """), {"oid": body.operator_id, "tip": body.izin_tipi,
           "bas": body.baslangic_tarihi, "bit": body.bitis_tarihi,
           "ac": body.aciklama})
    db.commit()
    return {"detail": "İzin talebi oluşturuldu"}


@router.patch("/izin/{izin_id}/onayla")
def izin_onayla(
    izin_id: int,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(require_yonetici),
):
    row = db.execute(text("SELECT Id, Durum FROM IzinTalepleri WHERE Id=:id"), {"id": izin_id}).fetchone()
    if not row:
        raise HTTPException(404, "İzin talebi bulunamadı")
    if row[1] != "bekliyor":
        raise HTTPException(400, "Bu talep zaten işleme alınmış")

    db.execute(text("""
        UPDATE IzinTalepleri
        SET Durum='onaylandi', OnaylayanId=:uid, OnayTarihi=GETUTCDATE()
        WHERE Id=:id
    """), {"uid": current_user.id, "id": izin_id})
    db.commit()
    return {"detail": "İzin onaylandı"}


@router.patch("/izin/{izin_id}/reddet")
def izin_reddet(
    izin_id: int,
    body: IzinOnayCreate,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(require_yonetici),
):
    row = db.execute(text("SELECT Id, Durum FROM IzinTalepleri WHERE Id=:id"), {"id": izin_id}).fetchone()
    if not row:
        raise HTTPException(404, "İzin talebi bulunamadı")
    if row[1] != "bekliyor":
        raise HTTPException(400, "Bu talep zaten işleme alınmış")

    db.execute(text("""
        UPDATE IzinTalepleri
        SET Durum='reddedildi', OnaylayanId=:uid, OnayTarihi=GETUTCDATE(), RedNedeni=:red
        WHERE Id=:id
    """), {"uid": current_user.id, "red": body.red_nedeni, "id": izin_id})
    db.commit()
    return {"detail": "İzin reddedildi"}


@router.delete("/izin/{izin_id}")
def izin_iptal(
    izin_id: int,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    db.execute(text("DELETE FROM IzinTalepleri WHERE Id=:id AND Durum='bekliyor'"), {"id": izin_id})
    db.commit()
    return {"detail": "İzin talebi silindi"}


@router.get("/ozet")
def vardiya_ozet(
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    """Dashboard için hızlı özet."""
    bugun = date.today()

    bugun_calisanlar = db.execute(text("""
        SELECT COUNT(*) FROM VardiyaPlani WHERE Tarih=:t
    """), {"t": bugun}).scalar()

    bekleyen_izin = db.execute(text("""
        SELECT COUNT(*) FROM IzinTalepleri WHERE Durum='bekliyor'
    """)).scalar()

    bu_hafta_izinli = db.execute(text("""
        SELECT COUNT(*) FROM IzinTalepleri
        WHERE Durum='onaylandi'
        AND BaslangicTarihi <= :bit AND BitisTarihi >= :bas
    """), {"bas": bugun, "bit": bugun + timedelta(days=6)}).scalar()

    tanimli_vardiya = db.execute(text("""
        SELECT COUNT(*) FROM VardiyaTanimlari WHERE Aktif=1
    """)).scalar()

    return {
        "bugun_calisanlar": int(bugun_calisanlar or 0),
        "bekleyen_izin": int(bekleyen_izin or 0),
        "bu_hafta_izinli": int(bu_hafta_izinli or 0),
        "tanimli_vardiya": int(tanimli_vardiya or 0),
    }


@router.post("/izin/benim", response_model=dict)
def kendi_izin_talebi_olustur(
    body: IzinTalebiCreate,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    """Tablet operatörü kendi adına izin talebi oluşturur — operator_id token'dan alınır."""
    # Kullanıcının operator kaydını bul
    op = db.execute(text("""
        SELECT Id FROM Operatorler WHERE KullaniciId = :uid AND Aktif = 1
    """), {"uid": current_user.id}).fetchone()

    if not op:
        raise HTTPException(400, "Bu kullanıcıya ait operatör kaydı bulunamadı")

    gecerli_tipler = ["yillik", "hastalik", "mazeret", "ucretsiz"]
    if body.izin_tipi not in gecerli_tipler:
        raise HTTPException(400, f"Geçersiz izin tipi")
    if body.bitis_tarihi < body.baslangic_tarihi:
        raise HTTPException(400, "Bitiş tarihi başlangıç tarihinden önce olamaz")

    db.execute(text("""
        INSERT INTO IzinTalepleri
            (OperatorId, IzinTipi, BaslangicTarihi, BitisTarihi, Aciklama)
        VALUES (:oid, :tip, :bas, :bit, :ac)
    """), {"oid": op[0], "tip": body.izin_tipi,
           "bas": body.baslangic_tarihi, "bit": body.bitis_tarihi,
           "ac": body.aciklama})
    db.commit()
    return {"detail": "İzin talebiniz iletildi"}