"""
Operatör Verimlilik Skoru — Tepki sürelerine dayalı performans analizi

Metrikler:
- Kabul Süresi      : İş emri atandıktan kabul edilene kadar (dk) — ne kadar kısa = iyi
- Başlatma Süresi   : Kabul'den üretime başlamaya kadar (dk) — ne kadar kısa = iyi
- Arıza Bildirme    : Arızanın bildirilme hızı (dk) — ne kadar kısa = iyi (log tablosundan)
- Kalite Oranı      : Kabul / Üretilen oranı — ne kadar yüksek = iyi
- Verimlilik Skoru  : Tüm metriklerin ağırlıklı ortalaması (0-100)
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel
from app.db.database import get_db
from app.models.models import Kullanici
from app.core.security import require_yonetici

router = APIRouter(prefix="/operator-performans", tags=["operator-performans"])


class OperatorDetayOut(BaseModel):
    operator_id: int
    ad_soyad: str
    sicil_no: str
    departman: Optional[str]
    # İş emri metrikleri
    tamamlanan_is: int
    ort_kabul_suresi_dk: Optional[float]   # bekliyor → kabul_edildi
    ort_baslama_suresi_dk: Optional[float] # kabul_edildi → basladi
    ort_is_suresi_dk: Optional[float]      # basladi → tamamlandi
    # Arıza metrikleri
    ariza_sayisi: int
    ort_ariza_sure_dk: Optional[float]     # arızanın ortalama süresi
    # Kalite
    toplam_uretilen: int
    toplam_kabul: int
    kalite_orani: Optional[float]          # %
    # Skor
    verimlilik_skoru: Optional[float]      # 0-100


class OperatorIsDetayOut(BaseModel):
    is_emri_no: str
    stok_adi: str
    makine_kodu: str
    olusturma_tarihi: datetime
    kabul_zamani: Optional[datetime]
    baslangic_zamani: Optional[datetime]
    bitis_zamani: Optional[datetime]
    kabul_suresi_dk: Optional[int]
    baslama_suresi_dk: Optional[int]
    is_suresi_dk: Optional[int]
    durum: str


def _hesapla_skor(kabul_dk, baslama_dk, kalite_oran, ariza_sayisi, is_sayisi) -> Optional[float]:
    """
    Verimlilik skoru hesaplama (0-100):
    - Kabul hızı (%30): Hedef < 5 dk, 0 = 0 puan, ≤5dk = 100 puan
    - Başlatma hızı (%20): Hedef < 10 dk
    - Kalite oranı (%35): Direkt 0-100
    - Arıza oranı (%15): is_sayisi/ariza_sayisi — az arıza = iyi
    """
    if not is_sayisi:
        return None

    puan = 0.0

    # Kabul hızı (30 puan)
    if kabul_dk is not None:
        if kabul_dk <= 2:
            puan += 30
        elif kabul_dk <= 5:
            puan += 25
        elif kabul_dk <= 15:
            puan += 18
        elif kabul_dk <= 30:
            puan += 10
        else:
            puan += max(0, 30 - (kabul_dk / 10))

    # Başlatma hızı (20 puan)
    if baslama_dk is not None:
        if baslama_dk <= 5:
            puan += 20
        elif baslama_dk <= 15:
            puan += 15
        elif baslama_dk <= 30:
            puan += 10
        else:
            puan += max(0, 20 - (baslama_dk / 15))

    # Kalite oranı (35 puan)
    if kalite_oran is not None:
        puan += (kalite_oran / 100) * 35
    else:
        puan += 35  # Kalite kaydı yoksa tam puan

    # Arıza oranı (15 puan) — az arıza = iyi
    if ariza_sayisi == 0:
        puan += 15
    else:
        ariza_oran = ariza_sayisi / is_sayisi
        if ariza_oran < 0.05:
            puan += 12
        elif ariza_oran < 0.1:
            puan += 8
        elif ariza_oran < 0.2:
            puan += 4
        else:
            puan += 0

    return round(min(100, puan), 1)


@router.get("/", response_model=List[OperatorDetayOut])
def operator_performans_listesi(
    baslangic: Optional[date] = Query(None),
    bitis: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    """Tüm operatörlerin verimlilik skorlarını döner."""

    tarih_filtre_mie = ""
    tarih_filtre_ariza = ""
    params = {}

    if baslangic:
        tarih_filtre_mie += " AND mie.OlusturmaTarihi >= :bas"
        tarih_filtre_ariza += " AND a.Baslangic >= :bas"
        params["bas"] = datetime.combine(baslangic, datetime.min.time())
    if bitis:
        tarih_filtre_mie += " AND mie.OlusturmaTarihi <= :bit"
        tarih_filtre_ariza += " AND a.Baslangic <= :bit"
        params["bit"] = datetime.combine(bitis, datetime.max.time())

    # Operatörleri çek
    ops = db.execute(text("""
        SELECT o.Id, k.AdSoyad, o.SicilNo, o.Departman
        FROM Operatorler o
        JOIN Kullanicilar k ON k.Id = o.KullaniciId
        WHERE o.Aktif = 1
        ORDER BY k.AdSoyad
    """)).fetchall()

    result = []
    for op_id, ad_soyad, sicil_no, departman in ops:
        p = dict(params)
        p["oid"] = op_id

        # İş emirleri — kabul ve başlatma süreleri
        is_rows = db.execute(text(f"""
            SELECT
                mie.Id,
                mie.OlusturmaTarihi,
                mie.BaslangicZamani,
                mie.BitisZamani,
                mie.Durum,
                -- Kabul log zamanı
                (SELECT TOP 1 ul.Zaman FROM UretimLoglari ul
                 WHERE ul.MakineIsEmriId = mie.Id
                 AND ul.IslemTipi = 'is_emri_kabul'
                 ORDER BY ul.Zaman ASC) AS KabulZamani
            FROM MakineIsEmirleri mie
            WHERE mie.OperatorId = :oid
            {tarih_filtre_mie}
            ORDER BY mie.OlusturmaTarihi DESC
        """), p).fetchall()

        tamamlananlar = [r for r in is_rows if r[4] == "tamamlandi"]

        kabul_sureleri = []
        baslama_sureleri = []
        is_sureleri = []

        for r in tamamlananlar:
            olusturma = r[2]  # OlusturmaTarihi yerine BaslangicZamani kullan
            kabul_z = r[5]
            baslangic_z = r[2]
            bitis_z = r[3]
            olusturma_z = r[1]

            # Kabul süresi: oluşturma → kabul
            if kabul_z and olusturma_z:
                dk = (kabul_z - olusturma_z).total_seconds() / 60
                if 0 <= dk <= 480:  # max 8 saat, mantıklı değer
                    kabul_sureleri.append(dk)

            # Başlatma süresi: kabul → başlangıç
            if kabul_z and baslangic_z:
                dk = (baslangic_z - kabul_z).total_seconds() / 60
                if 0 <= dk <= 480:
                    baslama_sureleri.append(dk)

            # İş süresi: başlangıç → bitiş
            if baslangic_z and bitis_z:
                dk = (bitis_z - baslangic_z).total_seconds() / 60
                if dk > 0:
                    is_sureleri.append(dk)

        ort_kabul = round(sum(kabul_sureleri) / len(kabul_sureleri), 1) if kabul_sureleri else None
        ort_baslama = round(sum(baslama_sureleri) / len(baslama_sureleri), 1) if baslama_sureleri else None
        ort_is = round(sum(is_sureleri) / len(is_sureleri), 1) if is_sureleri else None

        # Arıza sayısı ve süreleri
        ariza_rows = db.execute(text(f"""
            SELECT COUNT(*), AVG(DATEDIFF(MINUTE, a.Baslangic, ISNULL(a.Bitis, GETUTCDATE())))
            FROM Arizalar a
            WHERE a.OperatorId = :oid
            {tarih_filtre_ariza}
        """), p).fetchone()

        ariza_sayisi = int(ariza_rows[0] or 0)
        ort_ariza = float(ariza_rows[1]) if ariza_rows[1] else None

        # Kalite
        kk = db.execute(text(f"""
            SELECT SUM(kk.UretilenAdet), SUM(kk.KabulAdet)
            FROM KaliteKontrol kk
            JOIN MakineIsEmirleri mie ON mie.Id = kk.MakineIsEmriId
            WHERE kk.OperatorId = :oid
            {tarih_filtre_mie}
        """), p).fetchone()

        toplam_uretilen = int(kk[0] or 0)
        toplam_kabul = int(kk[1] or 0)
        kalite_oran = round((toplam_kabul / toplam_uretilen * 100), 1) if toplam_uretilen > 0 else None

        # Skor
        skor = _hesapla_skor(ort_kabul, ort_baslama, kalite_oran, ariza_sayisi, len(tamamlananlar))

        result.append(OperatorDetayOut(
            operator_id=op_id,
            ad_soyad=ad_soyad,
            sicil_no=sicil_no,
            departman=departman,
            tamamlanan_is=len(tamamlananlar),
            ort_kabul_suresi_dk=ort_kabul,
            ort_baslama_suresi_dk=ort_baslama,
            ort_is_suresi_dk=ort_is,
            ariza_sayisi=ariza_sayisi,
            ort_ariza_sure_dk=ort_ariza,
            toplam_uretilen=toplam_uretilen,
            toplam_kabul=toplam_kabul,
            kalite_orani=kalite_oran,
            verimlilik_skoru=skor,
        ))

    # Skora göre sırala
    result.sort(key=lambda x: (x.verimlilik_skoru or 0), reverse=True)
    return result


@router.get("/{operator_id}/is-detaylari", response_model=List[OperatorIsDetayOut])
def operator_is_detaylari(
    operator_id: int,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _: Kullanici = Depends(require_yonetici),
):
    """Operatörün iş emirlerinin detaylı tepki süreleri."""
    rows = db.execute(text("""
        SELECT
            ie.IsEmriNo,
            s.StokAdi,
            m.Kod,
            mie.OlusturmaTarihi,
            mie.BaslangicZamani,
            mie.BitisZamani,
            mie.Durum,
            (SELECT TOP 1 ul.Zaman FROM UretimLoglari ul
             WHERE ul.MakineIsEmriId = mie.Id
             AND ul.IslemTipi = 'is_emri_kabul'
             ORDER BY ul.Zaman ASC) AS KabulZamani
        FROM MakineIsEmirleri mie
        JOIN IsEmirleri ie ON ie.Id = mie.IsEmriId
        JOIN StokKartlari s ON s.Id = ie.StokId
        JOIN Makineler m ON m.Id = mie.MakineId
        WHERE mie.OperatorId = :oid
        ORDER BY mie.OlusturmaTarihi DESC
        OFFSET 0 ROWS FETCH NEXT :lim ROWS ONLY
    """), {"oid": operator_id, "lim": limit}).fetchall()

    result = []
    for r in rows:
        is_emri_no, stok_adi, makine_kodu = r[0], r[1], r[2]
        olusturma, baslangic_z, bitis_z, durum, kabul_z = r[3], r[4], r[5], r[6], r[7]

        kabul_dk = None
        baslama_dk = None
        is_dk = None

        if kabul_z and olusturma:
            d = (kabul_z - olusturma).total_seconds() / 60
            if 0 <= d <= 480:
                kabul_dk = int(d)

        if kabul_z and baslangic_z:
            d = (baslangic_z - kabul_z).total_seconds() / 60
            if 0 <= d <= 480:
                baslama_dk = int(d)

        if baslangic_z and bitis_z:
            d = (bitis_z - baslangic_z).total_seconds() / 60
            if d > 0:
                is_dk = int(d)

        result.append(OperatorIsDetayOut(
            is_emri_no=is_emri_no,
            stok_adi=stok_adi,
            makine_kodu=makine_kodu,
            olusturma_tarihi=olusturma,
            kabul_zamani=kabul_z,
            baslangic_zamani=baslangic_z,
            bitis_zamani=bitis_z,
            kabul_suresi_dk=kabul_dk,
            baslama_suresi_dk=baslama_dk,
            is_suresi_dk=is_dk,
            durum=durum,
        ))

    return result