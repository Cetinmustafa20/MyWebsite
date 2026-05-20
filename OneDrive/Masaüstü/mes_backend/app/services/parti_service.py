"""
Üretim Parti Servisi.
Üretim bittiğinde otomatik parti kodu ve QR içeriği oluşturur.
"""
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import (
    UretimPartisi, MakineIsEmri, IsEmri, Makine, Operator, Kullanici,
    StokKarti, KaliteKontrol, UretimSayaci
)
from sqlalchemy import func


def parti_kodu_olustur(makine_kodu: str, db: Session) -> str:
    """P-YYYYMMDD-M01-001 formatında benzersiz parti kodu oluştur."""
    bugun = datetime.utcnow().strftime("%Y%m%d")
    prefix = f"P{bugun}-{makine_kodu}"
    
    # Bugün kaç parti oluşturulmuş
    bugun_baslangic = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    sayi = db.query(UretimPartisi).filter(
        UretimPartisi.parti_kodu.like(f"{prefix}%"),
        UretimPartisi.olusturma_tarihi >= bugun_baslangic,
    ).count()
    
    return f"{prefix}-{str(sayi + 1).zfill(3)}"


def parti_olustur(db: Session, makine_is_emri_id: int) -> UretimPartisi:
    """Üretim tamamlandığında parti kaydı oluştur."""
    mie = db.query(MakineIsEmri).filter(MakineIsEmri.id == makine_is_emri_id).first()
    if not mie:
        raise ValueError("İş emri bulunamadı")

    ie = db.query(IsEmri).filter(IsEmri.id == mie.is_emri_id).first()
    makine = db.query(Makine).filter(Makine.id == mie.makine_id).first()
    operator = db.query(Operator).filter(Operator.id == mie.operator_id).first()
    kullanici = db.query(Kullanici).filter(Kullanici.id == operator.kullanici_id).first() if operator else None
    stok = db.query(StokKarti).filter(StokKarti.id == ie.stok_id).first() if ie else None

    # Toplam üretilen adet
    toplam_uretilen = db.query(func.sum(UretimSayaci.uretilen_adet)).filter(
        UretimSayaci.makine_is_emri_id == makine_is_emri_id
    ).scalar() or 0

    # Kalite verileri
    kk = db.query(
        func.sum(KaliteKontrol.kabul_adet),
        func.sum(KaliteKontrol.fire_adet),
    ).filter(KaliteKontrol.makine_is_emri_id == makine_is_emri_id).first()
    kabul_adet = kk[0] or 0
    fire_adet = kk[1] or 0

    parti_kodu = parti_kodu_olustur(makine.kod if makine else "UNK", db)

    # QR içeriği — JSON formatında
    qr_data = {
        "parti": parti_kodu,
        "urun": stok.stok_adi if stok else "-",
        "stok_kodu": stok.stok_kodu if stok else "-",
        "is_emri": ie.is_emri_no if ie else "-",
        "makine": makine.kod if makine else "-",
        "operator": kullanici.ad_soyad if kullanici else "-",
        "adet": toplam_uretilen,
        "tarih": datetime.utcnow().strftime("%d.%m.%Y %H:%M"),
    }
    qr_icerik = json.dumps(qr_data, ensure_ascii=False)

    parti = UretimPartisi(
        parti_kodu=parti_kodu,
        makine_is_emri_id=makine_is_emri_id,
        makine_id=mie.makine_id,
        operator_id=mie.operator_id,
        stok_id=ie.stok_id if ie else 1,
        is_emri_no=ie.is_emri_no if ie else "-",
        uretilen_adet=toplam_uretilen,
        kabul_adet=kabul_adet,
        fire_adet=fire_adet,
        baslangic_zamani=mie.baslangic_zamani or datetime.utcnow(),
        bitis_zamani=datetime.utcnow(),
        qr_icerik=qr_icerik,
    )
    db.add(parti)
    db.commit()
    db.refresh(parti)
    return parti
