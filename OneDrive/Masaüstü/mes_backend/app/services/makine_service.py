"""
Makine durum servisi - bildirimler eklenmiş versiyon.
"""
import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import Makine, MakineIsEmri, UretimLog, Ariza, IsEmri, Operator, Kullanici
from app.db.database import get_redis

redis_client = get_redis()
MAKINE_DURUM_KEY = "makine:durum:{makine_id}"


def get_makine_durumu_redis(makine_id: int) -> dict | None:
    key = MAKINE_DURUM_KEY.format(makine_id=makine_id)
    data = redis_client.get(key)
    return json.loads(data) if data else None


def set_makine_durumu_redis(makine_id: int, durum_data: dict):
    key = MAKINE_DURUM_KEY.format(makine_id=makine_id)
    redis_client.set(key, json.dumps(durum_data, default=str))


def get_tum_makine_durumlari() -> list[dict]:
    keys = redis_client.keys("makine:durum:*")
    if not keys:
        return []
    pipeline = redis_client.pipeline()
    for key in keys:
        pipeline.get(key)
    results = pipeline.execute()
    return [json.loads(r) for r in results if r]


def uretim_baslat(db: Session, makine_is_emri_id: int, operator_id: int) -> MakineIsEmri:
    mie = db.query(MakineIsEmri).filter(MakineIsEmri.id == makine_is_emri_id).first()
    if not mie:
        raise ValueError("İş emri bulunamadı")
    if mie.durum not in ("bekliyor", "kabul_edildi"):
        raise ValueError(f"Bu iş emri başlatılamaz: mevcut durum={mie.durum}")
    if mie.operator_id and mie.operator_id != operator_id:
        raise ValueError("Bu is emri baska bir operator tarafindan sahiplenilmis")
    aktif_uretim = db.query(MakineIsEmri).filter(
        MakineIsEmri.makine_id == mie.makine_id,
        MakineIsEmri.durum.in_(["basladi", "duraklatildi"]),
        MakineIsEmri.id != mie.id,
    ).first()
    if aktif_uretim:
        raise ValueError("Makinede zaten aktif bir uretim bulunuyor")
    onceki_durum = mie.durum
    now = datetime.utcnow()
    mie.durum = "basladi"
    mie.baslangic_zamani = now
    mie.operator_id = operator_id
    mie.guncelleme_tarihi = now
    makine = db.query(Makine).filter(Makine.id == mie.makine_id).first()
    makine.durum = "uretimde"
    makine.guncelleme_tarihi = now
    log = UretimLog(makine_is_emri_id=mie.id, islem_tipi="uretim_basladi", zaman=now,
                    operator_id=operator_id, makine_id=mie.makine_id,
                    onceki_durum=onceki_durum, yeni_durum="basladi")
    db.add(log)
    db.commit()
    db.refresh(mie)
    _redis_makine_guncelle(db, makine.id)
    return mie


def uretim_bitir(db: Session, makine_is_emri_id: int, operator_id: int) -> MakineIsEmri:
    mie = db.query(MakineIsEmri).filter(MakineIsEmri.id == makine_is_emri_id).first()
    if not mie or mie.durum not in ("basladi", "duraklatildi"):
        raise ValueError("Aktif üretim bulunamadı")
    if mie.operator_id and mie.operator_id != operator_id:
        raise ValueError("Bu uretim kaydi baska bir operator tarafindan yonetiliyor")
    now = datetime.utcnow()
    baslangic = mie.baslangic_zamani
    mie.durum = "tamamlandi"
    mie.bitis_zamani = now
    mie.guncelleme_tarihi = now
    makine = db.query(Makine).filter(Makine.id == mie.makine_id).first()
    makine.durum = "bosta"
    makine.guncelleme_tarihi = now
    log = UretimLog(makine_is_emri_id=mie.id, islem_tipi="uretim_bitti", zaman=now,
                    operator_id=operator_id, makine_id=mie.makine_id,
                    onceki_durum="basladi", yeni_durum="tamamlandi")
    db.add(log)
    db.commit()
    db.refresh(mie)
    _redis_makine_guncelle(db, makine.id)

    # Üretim tamamlandı bildirimi
    try:
        from app.services.bildirim_service import uretim_tamamlandi_bildirimi_gonder
        sure_dk = int((now - baslangic).total_seconds() / 60) if baslangic else 0
        op = db.query(Operator).filter(Operator.id == operator_id).first()
        k = db.query(Kullanici).filter(Kullanici.id == op.kullanici_id).first() if op else None
        ie = db.query(IsEmri).filter(IsEmri.id == mie.is_emri_id).first()
        uretim_tamamlandi_bildirimi_gonder(
            makine_kodu=makine.kod,
            is_emri_no=ie.is_emri_no if ie else "-",
            stok_adi=ie.stok.stok_adi if ie and ie.stok else "-",
            sure_dakika=sure_dk,
            operator_adi=k.ad_soyad if k else "-",
        )
    except Exception:
        pass

    return mie


def ariza_bildir(db: Session, makine_id: int, operator_id: int, ariza_tipi: str, aciklama: str) -> Ariza:
    now = datetime.utcnow()
    makine = db.query(Makine).filter(Makine.id == makine_id).first()
    if not makine:
        raise ValueError("Makine bulunamadı")
    acik_ariza = db.query(Ariza).filter(
        Ariza.makine_id == makine_id,
        Ariza.durum == "devam_ediyor",
    ).first()
    if acik_ariza:
        raise ValueError("Bu makine icin zaten acik bir ariza kaydi var")
    aktif_mie = db.query(MakineIsEmri).filter(
        MakineIsEmri.makine_id == makine_id, MakineIsEmri.durum == "basladi").first()
    if aktif_mie and aktif_mie.operator_id and aktif_mie.operator_id != operator_id:
        raise ValueError("Bu makinedeki aktif uretim baska bir operator tarafindan yonetiliyor")
    if aktif_mie:
        aktif_mie.durum = "duraklatildi"
        aktif_mie.guncelleme_tarihi = now
        log = UretimLog(makine_is_emri_id=aktif_mie.id, islem_tipi="ariza_nedeniyle_durduruldu",
                        zaman=now, operator_id=operator_id, makine_id=makine_id,
                        onceki_durum="basladi", yeni_durum="duraklatildi")
        db.add(log)
    ariza = Ariza(makine_id=makine_id, operator_id=operator_id, ariza_tipi=ariza_tipi,
                  aciklama=aciklama, baslangic=now, durum="devam_ediyor")
    db.add(ariza)
    makine.durum = "arizali"
    makine.guncelleme_tarihi = now
    db.commit()
    db.refresh(ariza)
    _redis_makine_guncelle(db, makine_id)

    # Arıza bildirimi
    try:
        from app.services.bildirim_service import ariza_bildirimi_gonder
        op = db.query(Operator).filter(Operator.id == operator_id).first()
        k = db.query(Kullanici).filter(Kullanici.id == op.kullanici_id).first() if op else None
        ariza_bildirimi_gonder(
            makine_kodu=makine.kod,
            makine_adi=makine.ad,
            ariza_tipi=ariza_tipi,
            aciklama=aciklama,
            operator_adi=k.ad_soyad if k else "-",
        )
    except Exception:
        pass

    return ariza


def _redis_makine_guncelle(db: Session, makine_id: int):
    """SQL'deki son durumu Redis'e yansıt — zenginleştirilmiş veri."""
    makine = db.query(Makine).filter(Makine.id == makine_id).first()
    if not makine:
        return

    aktif_mie = db.query(MakineIsEmri).filter(
        MakineIsEmri.makine_id == makine_id,
        MakineIsEmri.durum.in_(["basladi", "duraklatildi"]),
    ).first()

    aktif_ariza = db.query(Ariza).filter(
        Ariza.makine_id == makine_id, Ariza.durum == "devam_ediyor").first()

    operator_adi = None
    operator_sicil = None
    if aktif_mie and aktif_mie.operator_id:
        op = db.query(Operator).filter(Operator.id == aktif_mie.operator_id).first()
        if op:
            operator_sicil = op.sicil_no
            k = db.query(Kullanici).filter(Kullanici.id == op.kullanici_id).first()
            if k:
                operator_adi = k.ad_soyad

    is_emri_no = None
    stok_adi = None
    toplam_miktar = None

    if aktif_mie:
        ie = db.query(IsEmri).filter(IsEmri.id == aktif_mie.is_emri_id).first()
        if ie:
            is_emri_no = ie.is_emri_no
            toplam_miktar = ie.miktar
            if ie.stok:
                stok_adi = ie.stok.stok_adi

    toplam_durus_dk = 0
    if aktif_mie and aktif_mie.baslangic_zamani:
        arizalar = db.query(Ariza).filter(
            Ariza.makine_id == makine_id,
            Ariza.baslangic >= aktif_mie.baslangic_zamani,
        ).all()
        for a in arizalar:
            if a.bitis:
                toplam_durus_dk += int((a.bitis - a.baslangic).total_seconds() / 60)
            else:
                toplam_durus_dk += int((datetime.utcnow() - a.baslangic).total_seconds() / 60)

    kullanilabilirlik = None
    if aktif_mie and aktif_mie.baslangic_zamani:
        toplam_sure_dk = int((datetime.utcnow() - aktif_mie.baslangic_zamani).total_seconds() / 60)
        if toplam_sure_dk > 0:
            calisma = toplam_sure_dk - toplam_durus_dk
            kullanilabilirlik = round(max(0, min(100, (calisma / toplam_sure_dk) * 100)), 1)

    durum_data = {
        "makine_id": makine_id,
        "kod": makine.kod,
        "ad": makine.ad,
        "durum": makine.durum,
        "guncelleme": datetime.utcnow().isoformat(),
        "is_emri_id": aktif_mie.is_emri_id if aktif_mie else None,
        "is_emri_no": is_emri_no,
        "stok_adi": stok_adi,
        "toplam_miktar": toplam_miktar,
        "baslangic_zamani": aktif_mie.baslangic_zamani.isoformat() if aktif_mie and aktif_mie.baslangic_zamani else None,
        "operator_adi": operator_adi,
        "operator_sicil": operator_sicil,
        "toplam_durus_dk": toplam_durus_dk,
        "kullanilabilirlik": kullanilabilirlik,
        "ariza_tipi": aktif_ariza.ariza_tipi if aktif_ariza else None,
        "ariza_aciklama": aktif_ariza.aciklama if aktif_ariza else None,
        "ariza_baslangic": aktif_ariza.baslangic.isoformat() if aktif_ariza else None,
        "ariza_dakika": int((datetime.utcnow() - aktif_ariza.baslangic).total_seconds() / 60) if aktif_ariza else None,
    }
    set_makine_durumu_redis(makine_id, durum_data)
