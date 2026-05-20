"""
BOM (Bill of Materials) — Ürün Ağacı Endpoint'leri
Yarı Mamül ve Tam Mamül tanımları + üretim aşamaları
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.db.database import get_db
from app.models.models import StokKarti, Kullanici, Makine
from app.core.security import get_current_user, require_yonetici

router = APIRouter(prefix="/bom", tags=["bom"])


# ── PYDANTIC MODELLER ───────────────────────────────────────

class BomKalemCreate(BaseModel):
    malzeme_stok_id: int
    miktar: float
    birim: str
    fire_yuzdesi: float = 0.0
    notlar: Optional[str] = None

class BomAsamaCreate(BaseModel):
    asama_no: int
    asama_adi: str
    makine_id: Optional[int] = None
    sure_dakika: Optional[int] = None
    iscilik_saati: Optional[float] = None
    aciklama: Optional[str] = None
    kalemler: List[BomKalemCreate] = []

class BomCreate(BaseModel):
    urun_stok_id: int
    versiyon: str = "1.0"
    aciklama: Optional[str] = None
    asamalar: List[BomAsamaCreate] = []

class BomKalemOut(BaseModel):
    id: int
    malzeme_stok_id: int
    malzeme_kodu: str
    malzeme_adi: str
    malzeme_tipi: str
    miktar: float
    birim: str
    fire_yuzdesi: float
    notlar: Optional[str]

class BomAsamaOut(BaseModel):
    id: int
    asama_no: int
    asama_adi: str
    makine_id: Optional[int]
    makine_kodu: Optional[str]
    makine_adi: Optional[str]
    sure_dakika: Optional[int]
    iscilik_saati: Optional[float]
    aciklama: Optional[str]
    kalemler: List[BomKalemOut]

class BomOut(BaseModel):
    id: int
    urun_stok_id: int
    urun_kodu: str
    urun_adi: str
    urun_tipi: str
    versiyon: str
    aciklama: Optional[str]
    aktif: bool
    olusturma_tarihi: datetime
    asamalar: List[BomAsamaOut]

class StokTipGuncelle(BaseModel):
    urun_tipi: str  # "hammadde" | "yari_mamul" | "tam_mamul"


# ── STOK TİPİ YÖNETİMİ ─────────────────────────────────────

@router.patch("/stok/{stok_id}/tip", response_model=dict)
def stok_tip_guncelle(
    stok_id: int,
    body: StokTipGuncelle,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    gecerli_tipler = ["hammadde", "yari_mamul", "tam_mamul"]
    if body.urun_tipi not in gecerli_tipler:
        raise HTTPException(400, f"Geçersiz ürün tipi. Geçerli değerler: {gecerli_tipler}")

    stok = db.query(StokKarti).filter(StokKarti.id == stok_id).first()
    if not stok:
        raise HTTPException(404, "Stok kartı bulunamadı")

    stok.urun_tipi = body.urun_tipi
    db.commit()
    return {"detail": "Ürün tipi güncellendi", "urun_tipi": body.urun_tipi}


@router.get("/stok-tipleri")
def stok_tiplerini_listele(
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    """Tüm stok kartlarını tip bazında gruplu döner"""
    stoklar = db.query(StokKarti).filter(StokKarti.aktif == True).order_by(StokKarti.stok_kodu).all()
    return [
        {
            "id": s.id,
            "stok_kodu": s.stok_kodu,
            "stok_adi": s.stok_adi,
            "birim": s.birim,
            "kategori": s.kategori,
            "urun_tipi": s.urun_tipi or "hammadde",
            "aktif": s.aktif,
        }
        for s in stoklar
    ]


# ── BOM CRUD ────────────────────────────────────────────────

@router.get("/", response_model=List[BomOut])
def list_bomlar(
    urun_stok_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    from sqlalchemy import text
    try:
      # BomBaslik tablosunu sorgula
      q = db.execute(text("""
        SELECT b.Id, b.UrunStokId, s.StokKodu, s.StokAdi, s.UrunTipi,
               b.Versiyon, b.Aciklama, b.Aktif, b.OlusturmaTarihi
        FROM BomBasliklar b
        JOIN StokKartlari s ON s.Id = b.UrunStokId
        WHERE b.Aktif = 1
        """ + ("AND b.UrunStokId = :uid" if urun_stok_id else "") + """
        ORDER BY s.StokKodu
    """), {"uid": urun_stok_id} if urun_stok_id else {})

      result = []
      for row in q.fetchall():
          bom_id = row[0]
          asamalar = _get_asamalar(db, bom_id)
          result.append(BomOut(
              id=row[0], urun_stok_id=row[1], urun_kodu=row[2],
              urun_adi=row[3], urun_tipi=row[4] or "hammadde",
              versiyon=row[5], aciklama=row[6],
              aktif=bool(row[7]), olusturma_tarihi=row[8],
              asamalar=asamalar,
          ))
      return result
    except Exception as e:
      if "Invalid object name" in str(e) or "doesn't exist" in str(e) or "no such table" in str(e):
          raise HTTPException(500, "BOM tabloları oluşturulmamış. Önce bom_schema.sql dosyasını veritabanında çalıştırın.")
      raise


@router.get("/{bom_id}", response_model=BomOut)
def get_bom(
    bom_id: int,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    from sqlalchemy import text
    row = db.execute(text("""
        SELECT b.Id, b.UrunStokId, s.StokKodu, s.StokAdi, s.UrunTipi,
               b.Versiyon, b.Aciklama, b.Aktif, b.OlusturmaTarihi
        FROM BomBasliklar b
        JOIN StokKartlari s ON s.Id = b.UrunStokId
        WHERE b.Id = :id
    """), {"id": bom_id}).fetchone()

    if not row:
        raise HTTPException(404, "BOM bulunamadı")

    return BomOut(
        id=row[0], urun_stok_id=row[1], urun_kodu=row[2],
        urun_adi=row[3], urun_tipi=row[4] or "hammadde",
        versiyon=row[5], aciklama=row[6],
        aktif=bool(row[7]), olusturma_tarihi=row[8],
        asamalar=_get_asamalar(db, bom_id),
    )


@router.post("/", response_model=BomOut)
def create_bom(
    body: BomCreate,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    from sqlalchemy import text

    stok = db.query(StokKarti).filter(StokKarti.id == body.urun_stok_id).first()
    if not stok:
        raise HTTPException(404, "Ürün stok kartı bulunamadı")
    if stok.urun_tipi == "hammadde":
        raise HTTPException(400, "Hammadde için BOM tanımlanamaz. Önce ürün tipini yarı mamül veya tam mamül yapın.")

    # Aşama validasyonu
    for i, asama in enumerate(body.asamalar):
        if not asama.asama_adi or not asama.asama_adi.strip():
            raise HTTPException(400, f"Aşama {i+1} için ad zorunludur")

    # Aynı ürün + versiyon kombinasyonu var mı?
    mevcut = db.execute(text("""
        SELECT Id FROM BomBasliklar
        WHERE UrunStokId = :uid AND Versiyon = :v AND Aktif = 1
    """), {"uid": body.urun_stok_id, "v": body.versiyon}).fetchone()
    if mevcut:
        raise HTTPException(400, f"Bu ürün için '{body.versiyon}' versiyonu zaten tanımlı")

    # BomBaslik ekle — OUTPUT INSERTED.Id ile aynı sorguda ID al
    row = db.execute(text("""
        INSERT INTO BomBasliklar (UrunStokId, Versiyon, Aciklama, Aktif, OlusturmaTarihi)
        OUTPUT INSERTED.Id
        VALUES (:uid, :v, :ac, 1, GETUTCDATE())
    """), {"uid": body.urun_stok_id, "v": body.versiyon, "ac": body.aciklama or None}).fetchone()
    bom_id = row[0]

    # Aşamaları ekle
    for asama in body.asamalar:
        asama_row = db.execute(text("""
            INSERT INTO BomAsamalar (BomId, AsamaNo, AsamaAdi, MakineId, SureDakika, IscilkSaati, Aciklama)
            OUTPUT INSERTED.Id
            VALUES (:bom, :no, :ad, :mid, :sure, :is, :ac)
        """), {
            "bom": bom_id, "no": asama.asama_no, "ad": asama.asama_adi,
            "mid": asama.makine_id or None, "sure": asama.sure_dakika,
            "is": asama.iscilik_saati, "ac": asama.aciklama
        }).fetchone()
        asama_id = asama_row[0]

        for kalem in asama.kalemler:
            if kalem.fire_yuzdesi > 100:
                raise HTTPException(400, f"Fire yüzdesi 100 den büyük olamaz (girilen: {kalem.fire_yuzdesi}). Yuzde olarak girin, ornek: 15 fire icin 15 yazin.")
            db.execute(text("""
                INSERT INTO BomKalemler (BomAsamaId, MalzemeStokId, Miktar, Birim, FireYuzdesi, Notlar)
                VALUES (:aid, :mid, :m, :b, :f, :n)
            """), {
                "aid": asama_id, "mid": kalem.malzeme_stok_id,
                "m": kalem.miktar, "b": kalem.birim,
                "f": kalem.fire_yuzdesi, "n": kalem.notlar
            })

    db.commit()
    return get_bom(int(bom_id), db, _)



# ── BOM GÜNCELLE ────────────────────────────────────────────

class BomGuncelleRequest(BaseModel):
    versiyon: Optional[str] = None
    aciklama: Optional[str] = None
    asamalar: Optional[List[BomAsamaCreate]] = None

@router.put("/{bom_id}", response_model=BomOut)
def update_bom(
    bom_id: int,
    body: BomGuncelleRequest,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    from sqlalchemy import text

    row = db.execute(text("SELECT Id, UrunStokId FROM BomBasliklar WHERE Id = :id AND Aktif = 1"), {"id": bom_id}).fetchone()
    if not row:
        raise HTTPException(404, "BOM bulunamadı")

    # Başlık güncelle
    updates = []
    params = {"id": bom_id}
    if body.versiyon is not None:
        updates.append("Versiyon = :v")
        params["v"] = body.versiyon
    if body.aciklama is not None:
        updates.append("Aciklama = :ac")
        params["ac"] = body.aciklama or None
    if updates:
        db.execute(text(f"UPDATE BomBasliklar SET {', '.join(updates)} WHERE Id = :id"), params)

    # Aşamaları sıfırdan yaz
    if body.asamalar is not None:
        for i, asama in enumerate(body.asamalar):
            if not asama.asama_adi or not asama.asama_adi.strip():
                raise HTTPException(400, f"Aşama {i+1} için ad zorunludur")

        # Eski aşama ve kalemleri sil
        eski_asamalar = db.execute(text("SELECT Id FROM BomAsamalar WHERE BomId = :bid"), {"bid": bom_id}).fetchall()
        for a in eski_asamalar:
            db.execute(text("DELETE FROM BomKalemler WHERE BomAsamaId = :aid"), {"aid": a[0]})
        db.execute(text("DELETE FROM BomAsamalar WHERE BomId = :bid"), {"bid": bom_id})

        # Yeni aşamaları ekle
        for asama in body.asamalar:
            asama_row = db.execute(text("""
                INSERT INTO BomAsamalar (BomId, AsamaNo, AsamaAdi, MakineId, SureDakika, IscilkSaati, Aciklama)
                OUTPUT INSERTED.Id
                VALUES (:bom, :no, :ad, :mid, :sure, :is, :ac)
            """), {
                "bom": bom_id, "no": asama.asama_no, "ad": asama.asama_adi,
                "mid": asama.makine_id or None, "sure": asama.sure_dakika,
                "is": asama.iscilik_saati, "ac": asama.aciklama
            }).fetchone()
            asama_id = asama_row[0]

            for kalem in asama.kalemler:
                if kalem.fire_yuzdesi > 100:
                    raise HTTPException(400, f"Fire yüzdesi 100 den büyük olamaz")
                db.execute(text("""
                    INSERT INTO BomKalemler (BomAsamaId, MalzemeStokId, Miktar, Birim, FireYuzdesi, Notlar)
                    VALUES (:aid, :mid, :m, :b, :f, :n)
                """), {
                    "aid": asama_id, "mid": kalem.malzeme_stok_id,
                    "m": kalem.miktar, "b": kalem.birim,
                    "f": kalem.fire_yuzdesi, "n": kalem.notlar
                })

    db.commit()
    return get_bom(bom_id, db, _)

@router.delete("/{bom_id}")
def delete_bom(
    bom_id: int,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    from sqlalchemy import text
    row = db.execute(text("SELECT Id FROM BomBasliklar WHERE Id = :id"), {"id": bom_id}).fetchone()
    if not row:
        raise HTTPException(404, "BOM bulunamadı")
    db.execute(text("UPDATE BomBasliklar SET Aktif = 0 WHERE Id = :id"), {"id": bom_id})
    db.commit()
    return {"detail": "BOM silindi"}


def _get_asamalar(db: Session, bom_id: int) -> List[BomAsamaOut]:
    from sqlalchemy import text

    asamalar_raw = db.execute(text("""
        SELECT a.Id, a.AsamaNo, a.AsamaAdi, a.MakineId,
               m.Kod, m.Ad, a.SureDakika, a.IscilkSaati, a.Aciklama
        FROM BomAsamalar a
        LEFT JOIN Makineler m ON m.Id = a.MakineId
        WHERE a.BomId = :bid
        ORDER BY a.AsamaNo
    """), {"bid": bom_id}).fetchall()

    asamalar = []
    for a in asamalar_raw:
        kalemler_raw = db.execute(text("""
            SELECT k.Id, k.MalzemeStokId, s.StokKodu, s.StokAdi, s.UrunTipi,
                   k.Miktar, k.Birim, k.FireYuzdesi, k.Notlar
            FROM BomKalemler k
            JOIN StokKartlari s ON s.Id = k.MalzemeStokId
            WHERE k.BomAsamaId = :aid
        """), {"aid": a[0]}).fetchall()

        kalemler = [
            BomKalemOut(
                id=k[0], malzeme_stok_id=k[1], malzeme_kodu=k[2],
                malzeme_adi=k[3], malzeme_tipi=k[4] or "hammadde",
                miktar=float(k[5]), birim=k[6],
                fire_yuzdesi=float(k[7] or 0), notlar=k[8],
            )
            for k in kalemler_raw
        ]

        asamalar.append(BomAsamaOut(
            id=a[0], asama_no=a[1], asama_adi=a[2],
            makine_id=a[3], makine_kodu=a[4], makine_adi=a[5],
            sure_dakika=a[6], iscilik_saati=float(a[7]) if a[7] else None,
            aciklama=a[8], kalemler=kalemler,
        ))

    return asamalar


# ── İŞ EMRİ → BOM ───────────────────────────────────────────

@router.get("/is-emri/{makine_is_emri_id}", response_model=Optional[BomOut])
def get_bom_by_is_emri(
    makine_is_emri_id: int,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    """Makine iş emri ID'sinden ürünün BOM'unu döner"""
    from sqlalchemy import text
    from app.models.models import MakineIsEmri, IsEmri

    mie = db.query(MakineIsEmri).filter(MakineIsEmri.id == makine_is_emri_id).first()
    if not mie:
        raise HTTPException(404, "İş emri bulunamadı")

    ie = db.query(IsEmri).filter(IsEmri.id == mie.is_emri_id).first()
    if not ie:
        raise HTTPException(404, "İş emri detayı bulunamadı")

    row = db.execute(text("""
        SELECT b.Id, b.UrunStokId, s.StokKodu, s.StokAdi, s.UrunTipi,
               b.Versiyon, b.Aciklama, b.Aktif, b.OlusturmaTarihi
        FROM BomBasliklar b
        JOIN StokKartlari s ON s.Id = b.UrunStokId
        WHERE b.UrunStokId = :sid AND b.Aktif = 1
        ORDER BY b.Id DESC
    """), {"sid": ie.stok_id}).fetchone()

    if not row:
        return None

    return BomOut(
        id=row[0], urun_stok_id=row[1], urun_kodu=row[2],
        urun_adi=row[3], urun_tipi=row[4] or "hammadde",
        versiyon=row[5], aciklama=row[6],
        aktif=bool(row[7]), olusturma_tarihi=row[8],
        asamalar=_get_asamalar(db, row[0]),
    )