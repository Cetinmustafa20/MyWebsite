"""
Stok Hareketi Servisi + Endpoint'leri
Her BOM aşaması tamamlandığında ilgili malzemeleri stoktan düşer.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.db.database import get_db
from app.models.models import StokKarti, Kullanici, MakineIsEmri, IsEmri
from app.core.security import get_current_user, require_yonetici

router = APIRouter(prefix="/stok-hareket", tags=["stok-hareket"])


# ── PYDANTIC ────────────────────────────────────────────────

class StokGirisRequest(BaseModel):
    stok_id: int
    miktar: float
    birim_fiyat: Optional[float] = None
    aciklama: Optional[str] = None

class AsamaTamamlaRequest(BaseModel):
    makine_is_emri_id: int
    bom_asama_id: int

class StokHareketOut(BaseModel):
    id: int
    stok_id: int
    stok_kodu: str
    stok_adi: str
    hareket_tipi: str
    miktar: float
    onceki_bakiye: float
    sonraki_bakiye: float
    aciklama: Optional[str]
    olusturma_tarihi: datetime

class StokBakiyeOut(BaseModel):
    id: int
    stok_kodu: str
    stok_adi: str
    birim: str
    urun_tipi: str
    mevcut_miktar: float
    min_stok: Optional[float]
    kritik_seviye: bool


# ── SERVİS FONKSİYONLARI ────────────────────────────────────

def stok_duş(db: Session, stok_id: int, miktar: float,
              makine_is_emri_id: int = None, bom_asama_id: int = None,
              aciklama: str = None, olusturan_id: int = None) -> dict:
    """Stoktan miktar düş, hareket kaydı oluştur."""
    row = db.execute(text("""
        SELECT Id, StokAdi, Birim, ISNULL(MevcutMiktar, 0)
        FROM StokKartlari WHERE Id = :sid
    """), {"sid": stok_id}).fetchone()

    if not row:
        raise ValueError(f"Stok kartı bulunamadı: {stok_id}")

    stok_adi = row[1]
    birim = row[2]
    mevcut = float(row[3])

    if mevcut < miktar:
        raise ValueError(
            f"{stok_adi} için yeterli stok yok. "
            f"Mevcut: {mevcut} {birim}, Gerekli: {miktar} {birim}"
        )

    onceki = mevcut
    sonraki = round(mevcut - miktar, 3)

    db.execute(text("""
        UPDATE StokKartlari SET MevcutMiktar = :yeni WHERE Id = :sid
    """), {"yeni": sonraki, "sid": stok_id})

    db.execute(text("""
        INSERT INTO StokHareketleri
            (StokId, HareketTipi, Miktar, MakineIsEmriId, BomAsamaId,
             Aciklama, OncekiBakiye, SonrakiBakiye, OlusturanId, OlusturmaTarihi)
        VALUES
            (:sid, 'cikis', :m, :mie, :bom,
             :ac, :ob, :sb, :oid, GETUTCDATE())
    """), {
        "sid": stok_id, "m": miktar,
        "mie": makine_is_emri_id, "bom": bom_asama_id,
        "ac": aciklama, "ob": onceki, "sb": sonraki,
        "oid": olusturan_id
    })

    return {"stok_id": stok_id, "stok_adi": stok_adi,
            "dusülen": miktar, "yeni_bakiye": sonraki}


def stok_gir(db: Session, stok_id: int, miktar: float,
             birim_fiyat: float = None, aciklama: str = None,
             olusturan_id: int = None) -> dict:
    """Stoğa miktar ekle."""
    row = db.execute(text("""
        SELECT Id, StokAdi, ISNULL(MevcutMiktar, 0)
        FROM StokKartlari WHERE Id = :sid
    """), {"sid": stok_id}).fetchone()

    if not row:
        raise ValueError(f"Stok kartı bulunamadı: {stok_id}")

    stok_adi = row[1]
    onceki = float(row[2])
    sonraki = round(onceki + miktar, 3)

    db.execute(text("""
        UPDATE StokKartlari SET MevcutMiktar = :yeni WHERE Id = :sid
    """), {"yeni": sonraki, "sid": stok_id})

    db.execute(text("""
        INSERT INTO StokHareketleri
            (StokId, HareketTipi, Miktar, BirimFiyat,
             Aciklama, OncekiBakiye, SonrakiBakiye, OlusturanId, OlusturmaTarihi)
        VALUES
            (:sid, 'giris', :m, :bp,
             :ac, :ob, :sb, :oid, GETUTCDATE())
    """), {
        "sid": stok_id, "m": miktar, "bp": birim_fiyat,
        "ac": aciklama, "ob": onceki, "sb": sonraki,
        "oid": olusturan_id
    })

    return {"stok_id": stok_id, "stok_adi": stok_adi,
            "eklenen": miktar, "yeni_bakiye": sonraki}


# ── ENDPOINT'LER ─────────────────────────────────────────────

@router.get("/bakiye", response_model=List[StokBakiyeOut])
def stok_bakiye_listesi(
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    rows = db.execute(text("""
        SELECT Id, StokKodu, StokAdi, Birim,
               ISNULL(UrunTipi, 'hammadde'),
               ISNULL(MevcutMiktar, 0),
               MinStok
        FROM StokKartlari
        WHERE Aktif = 1
        ORDER BY StokKodu
    """)).fetchall()
    return [
        StokBakiyeOut(
            id=r[0], stok_kodu=r[1], stok_adi=r[2],
            birim=r[3], urun_tipi=r[4],
            mevcut_miktar=float(r[5]),
            min_stok=float(r[6]) if r[6] is not None else None,
            kritik_seviye=bool(r[6] is not None and float(r[5]) <= float(r[6])),
        )
        for r in rows
    ]


@router.post("/giris")
def stok_giris_yap(
    body: StokGirisRequest,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(require_yonetici),
):
    """Manuel stok girişi."""
    try:
        sonuc = stok_gir(
            db, body.stok_id, body.miktar,
            birim_fiyat=body.birim_fiyat,
            aciklama=body.aciklama or "Manuel giriş",
            olusturan_id=current_user.id,
        )
        db.commit()
        return {"detail": "Stok girişi yapıldı", **sonuc}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/asama-tamamla")
def asama_tamamla(
    body: AsamaTamamlaRequest,
    db: Session = Depends(get_db),
    current_user: Kullanici = Depends(get_current_user),
):
    """
    BOM aşaması tamamlandığında o aşamanın malzemelerini stoktan düş.
    Tablet operatörü her aşama bitişinde bu endpoint'i çağırır.
    """
    # Makine iş emrini doğrula
    mie = db.query(MakineIsEmri).filter(MakineIsEmri.id == body.makine_is_emri_id).first()
    if not mie:
        raise HTTPException(404, "İş emri bulunamadı")
    if mie.durum not in ("basladi", "duraklatildi"):
        raise HTTPException(400, "Üretim aktif değil")

    # BOM aşamasını ve kalemlerini getir
    asama_row = db.execute(text("""
        SELECT a.Id, a.AsamaNo, a.AsamaAdi, b.UrunStokId
        FROM BomAsamalar a
        JOIN BomBasliklar b ON b.Id = a.BomId
        WHERE a.Id = :aid AND b.Aktif = 1
    """), {"aid": body.bom_asama_id}).fetchone()

    if not asama_row:
        raise HTTPException(404, "BOM aşaması bulunamadı")

    kalemler = db.execute(text("""
        SELECT k.MalzemeStokId, k.Miktar, k.FireYuzdesi, s.StokAdi, s.Birim
        FROM BomKalemler k
        JOIN StokKartlari s ON s.Id = k.MalzemeStokId
        WHERE k.BomAsamaId = :aid
    """), {"aid": body.bom_asama_id}).fetchall()

    if not kalemler:
        return {"detail": "Bu aşamada malzeme kalemi yok, stok hareketi oluşturulmadı", "hareketler": []}

    # İş emrinin miktar çarpanını bul
    ie = db.query(IsEmri).filter(IsEmri.id == mie.is_emri_id).first()
    uretim_miktari = ie.miktar if ie else 1

    hareketler = []
    hatalar = []

    for k in kalemler:
        stok_id, bom_miktar, fire_yuzdesi, stok_adi, birim = k
        # Toplam düşülecek: BOM miktarı × üretim miktarı × (1 + fire/100)
        fire_carpani = 1 + (float(fire_yuzdesi or 0) / 100)
        toplam_miktar = round(float(bom_miktar) * uretim_miktari * fire_carpani, 3)

        try:
            sonuc = stok_duş(
                db, stok_id, toplam_miktar,
                makine_is_emri_id=body.makine_is_emri_id,
                bom_asama_id=body.bom_asama_id,
                aciklama=f"Aşama: {asama_row[2]} | İş Emri: {ie.is_emri_no if ie else '-'}",
                olusturan_id=current_user.id,
            )
            hareketler.append({
                "stok_adi": stok_adi,
                "dusülen_miktar": toplam_miktar,
                "birim": birim,
                "yeni_bakiye": sonuc["yeni_bakiye"],
            })
        except ValueError as e:
            hatalar.append(str(e))

    if hatalar:
        db.rollback()
        raise HTTPException(400, " | ".join(hatalar))

    db.commit()

    return {
        "detail": f"'{asama_row[2]}' aşaması tamamlandı, {len(hareketler)} malzeme stoktan düşüldü",
        "asama_adi": asama_row[2],
        "asama_no": asama_row[1],
        "hareketler": hareketler,
    }


@router.get("/hareketler", response_model=List[StokHareketOut])
def stok_hareketleri(
    stok_id: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    q = """
        SELECT h.Id, h.StokId, s.StokKodu, s.StokAdi,
               h.HareketTipi, h.Miktar,
               h.OncekiBakiye, h.SonrakiBakiye,
               h.Aciklama, h.OlusturmaTarihi
        FROM StokHareketleri h
        JOIN StokKartlari s ON s.Id = h.StokId
        {where}
        ORDER BY h.OlusturmaTarihi DESC
        OFFSET 0 ROWS FETCH NEXT :limit ROWS ONLY
    """
    params = {"limit": limit}
    where = "WHERE h.StokId = :sid" if stok_id else ""
    if stok_id:
        params["sid"] = stok_id

    rows = db.execute(text(q.format(where=where)), params).fetchall()

    return [
        StokHareketOut(
            id=r[0], stok_id=r[1], stok_kodu=r[2], stok_adi=r[3],
            hareket_tipi=r[4], miktar=float(r[5]),
            onceki_bakiye=float(r[6]), sonraki_bakiye=float(r[7]),
            aciklama=r[8], olusturma_tarihi=r[9],
        )
        for r in rows
    ]
