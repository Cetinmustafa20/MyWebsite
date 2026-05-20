"""
Üretim Geçmişi & Analitik Endpoint'leri
- Ürün bazlı geçmiş
- Operatör bazlı geçmiş
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel
from app.db.database import get_db
from app.models.models import Kullanici
from app.core.security import get_current_user

router = APIRouter(prefix="/gecmis", tags=["gecmis"])


# ── ÜRÜN BAZLI ──────────────────────────────────────────────

class UrunGecimiAylik(BaseModel):
    yil: int
    ay: int
    ay_adi: str
    uretim_sayisi: int
    toplam_miktar: int
    ort_sure_dk: Optional[float]
    kalite_orani: Optional[float]

class UrunGecmisDetay(BaseModel):
    stok_id: int
    stok_kodu: str
    stok_adi: str
    toplam_uretim: int
    toplam_miktar: int
    ort_sure_dk: Optional[float]
    kalite_orani: Optional[float]
    ilk_uretim: Optional[datetime]
    son_uretim: Optional[datetime]
    aylik: List[UrunGecimiAylik]

class UrunListeOut(BaseModel):
    stok_id: int
    stok_kodu: str
    stok_adi: str
    toplam_uretim: int
    toplam_miktar: int
    son_uretim: Optional[datetime]

class IsEmriGecmisOut(BaseModel):
    is_emri_no: str
    makine_kodu: str
    operator_adi: Optional[str]
    miktar: int
    baslangic: Optional[datetime]
    bitis: Optional[datetime]
    sure_dk: Optional[int]
    kalite_orani: Optional[float]
    durum: str


# ── OPERATÖR BAZLI ──────────────────────────────────────────

class OperatorAylikOut(BaseModel):
    yil: int
    ay: int
    ay_adi: str
    tamamlanan_is: int
    ort_kabul_suresi_dk: Optional[float]
    kalite_orani: Optional[float]
    verimlilik_skoru: Optional[float]

class OperatorGecmisOut(BaseModel):
    operator_id: int
    ad_soyad: str
    sicil_no: str
    toplam_is: int
    ort_kabul_suresi_dk: Optional[float]
    kalite_orani: Optional[float]
    ilk_is: Optional[datetime]
    son_is: Optional[datetime]
    aylik: List[OperatorAylikOut]


# ── YARDIMCI ────────────────────────────────────────────────

AY_ADLARI = ['', 'Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz',
              'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']


# ── ÜRÜN LİSTESİ ────────────────────────────────────────────

@router.get("/urunler", response_model=List[UrunListeOut])
def urun_listesi(
    baslangic: Optional[date] = None,
    bitis: Optional[date] = None,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    """Üretilmiş ürünlerin özet listesi."""
    where = "WHERE mie.Durum = 'tamamlandi'"
    params = {}
    if baslangic:
        where += " AND mie.BitisZamani >= :bas"
        params["bas"] = datetime.combine(baslangic, datetime.min.time())
    if bitis:
        where += " AND mie.BitisZamani <= :bit"
        params["bit"] = datetime.combine(bitis, datetime.max.time())

    rows = db.execute(text(f"""
        SELECT
            s.Id, s.StokKodu, s.StokAdi,
            COUNT(DISTINCT ie.Id) AS UretimSayisi,
            SUM(ie.Miktar) AS ToplamMiktar,
            MAX(mie.BitisZamani) AS SonUretim
        FROM IsEmirleri ie
        JOIN StokKartlari s ON s.Id = ie.StokId
        JOIN MakineIsEmirleri mie ON mie.IsEmriId = ie.Id
        {where}
        GROUP BY s.Id, s.StokKodu, s.StokAdi
        ORDER BY SonUretim DESC
    """), params).fetchall()

    return [UrunListeOut(
        stok_id=r[0], stok_kodu=r[1], stok_adi=r[2],
        toplam_uretim=int(r[3] or 0),
        toplam_miktar=int(r[4] or 0),
        son_uretim=r[5],
    ) for r in rows]


@router.get("/urunler/{stok_id}", response_model=UrunGecmisDetay)
def urun_gecmis_detay(
    stok_id: int,
    yil: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    """Bir ürünün tüm üretim geçmişi ve aylık trendi."""

    # Ürün bilgisi
    stok = db.execute(text("""
        SELECT Id, StokKodu, StokAdi FROM StokKartlari WHERE Id = :id
    """), {"id": stok_id}).fetchone()
    if not stok:
        from fastapi import HTTPException
        raise HTTPException(404, "Ürün bulunamadı")

    # Genel özet
    ozet = db.execute(text("""
        SELECT
            COUNT(DISTINCT ie.Id),
            SUM(ie.Miktar),
            AVG(DATEDIFF(MINUTE, mie.BaslangicZamani, mie.BitisZamani)),
            MIN(mie.BaslangicZamani),
            MAX(mie.BitisZamani)
        FROM IsEmirleri ie
        JOIN MakineIsEmirleri mie ON mie.IsEmriId = ie.Id
        WHERE ie.StokId = :sid AND mie.Durum = 'tamamlandi'
        AND mie.BaslangicZamani IS NOT NULL AND mie.BitisZamani IS NOT NULL
    """), {"sid": stok_id}).fetchone()

    # Kalite
    kal = db.execute(text("""
        SELECT SUM(kk.UretilenAdet), SUM(kk.KabulAdet)
        FROM KaliteKontrol kk
        JOIN MakineIsEmirleri mie ON mie.Id = kk.MakineIsEmriId
        JOIN IsEmirleri ie ON ie.Id = mie.IsEmriId
        WHERE ie.StokId = :sid
    """), {"sid": stok_id}).fetchone()

    kalite_oran = None
    if kal and kal[0] and kal[0] > 0:
        kalite_oran = round(kal[1] / kal[0] * 100, 1)

    # Aylık trend
    yil_filtre = f"AND YEAR(mie.BitisZamani) = {yil}" if yil else ""
    aylik_rows = db.execute(text(f"""
        SELECT
            YEAR(mie.BitisZamani) AS Yil,
            MONTH(mie.BitisZamani) AS Ay,
            COUNT(DISTINCT ie.Id) AS UretimSayisi,
            SUM(ie.Miktar) AS ToplamMiktar,
            AVG(DATEDIFF(MINUTE, mie.BaslangicZamani, mie.BitisZamani)) AS OrtSure
        FROM IsEmirleri ie
        JOIN MakineIsEmirleri mie ON mie.IsEmriId = ie.Id
        WHERE ie.StokId = :sid AND mie.Durum = 'tamamlandi'
        AND mie.BitisZamani IS NOT NULL
        {yil_filtre}
        GROUP BY YEAR(mie.BitisZamani), MONTH(mie.BitisZamani)
        ORDER BY Yil, Ay
    """), {"sid": stok_id}).fetchall()

    # Aylık kalite
    aylik_kal = db.execute(text(f"""
        SELECT
            YEAR(mie.BitisZamani) AS Yil,
            MONTH(mie.BitisZamani) AS Ay,
            SUM(kk.UretilenAdet),
            SUM(kk.KabulAdet)
        FROM KaliteKontrol kk
        JOIN MakineIsEmirleri mie ON mie.Id = kk.MakineIsEmriId
        JOIN IsEmirleri ie ON ie.Id = mie.IsEmriId
        WHERE ie.StokId = :sid AND mie.BitisZamani IS NOT NULL
        {yil_filtre}
        GROUP BY YEAR(mie.BitisZamani), MONTH(mie.BitisZamani)
    """), {"sid": stok_id}).fetchall()

    kal_map = {(r[0], r[1]): (r[2], r[3]) for r in aylik_kal}

    aylik = []
    for r in aylik_rows:
        yil_v, ay_v = r[0], r[1]
        k = kal_map.get((yil_v, ay_v))
        kal_oran_ay = round(k[1] / k[0] * 100, 1) if k and k[0] else None
        aylik.append(UrunGecimiAylik(
            yil=yil_v, ay=ay_v,
            ay_adi=f"{AY_ADLARI[ay_v]} {yil_v}",
            uretim_sayisi=int(r[2] or 0),
            toplam_miktar=int(r[3] or 0),
            ort_sure_dk=float(r[4]) if r[4] else None,
            kalite_orani=kal_oran_ay,
        ))

    return UrunGecmisDetay(
        stok_id=stok[0], stok_kodu=stok[1], stok_adi=stok[2],
        toplam_uretim=int(ozet[0] or 0),
        toplam_miktar=int(ozet[1] or 0),
        ort_sure_dk=float(ozet[2]) if ozet[2] else None,
        kalite_orani=kalite_oran,
        ilk_uretim=ozet[3],
        son_uretim=ozet[4],
        aylik=aylik,
    )


@router.get("/urunler/{stok_id}/is-emirleri", response_model=List[IsEmriGecmisOut])
def urun_is_emirleri(
    stok_id: int,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    """Bir ürünün tüm iş emirleri."""
    rows = db.execute(text("""
        SELECT
            ie.IsEmriNo, m.Kod,
            k.AdSoyad,
            ie.Miktar,
            mie.BaslangicZamani, mie.BitisZamani,
            DATEDIFF(MINUTE, mie.BaslangicZamani, mie.BitisZamani),
            ie.Durum
        FROM IsEmirleri ie
        JOIN MakineIsEmirleri mie ON mie.IsEmriId = ie.Id
        JOIN Makineler m ON m.Id = mie.MakineId
        LEFT JOIN Operatorler o ON o.Id = mie.OperatorId
        LEFT JOIN Kullanicilar k ON k.Id = o.KullaniciId
        WHERE ie.StokId = :sid
        ORDER BY ie.OlusturmaTarihi DESC
        OFFSET 0 ROWS FETCH NEXT :lim ROWS ONLY
    """), {"sid": stok_id, "lim": limit}).fetchall()

    result = []
    for r in rows:
        # Kalite
        kal = db.execute(text("""
            SELECT SUM(UretilenAdet), SUM(KabulAdet)
            FROM KaliteKontrol kk
            JOIN MakineIsEmirleri mie ON mie.Id = kk.MakineIsEmriId
            JOIN IsEmirleri ie ON ie.Id = mie.IsEmriId
            WHERE ie.IsEmriNo = :no
        """), {"no": r[0]}).fetchone()
        kal_oran = round(kal[1] / kal[0] * 100, 1) if kal and kal[0] else None

        result.append(IsEmriGecmisOut(
            is_emri_no=r[0], makine_kodu=r[1], operator_adi=r[2],
            miktar=int(r[3] or 0),
            baslangic=r[4], bitis=r[5],
            sure_dk=int(r[6]) if r[6] else None,
            kalite_orani=kal_oran,
            durum=r[7],
        ))
    return result


# ── OPERATÖR BAZLI ──────────────────────────────────────────

@router.get("/operatorler/{operator_id}", response_model=OperatorGecmisOut)
def operator_gecmis(
    operator_id: int,
    yil: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    """Bir operatörün üretim geçmişi ve aylık trend."""

    op = db.execute(text("""
        SELECT o.Id, k.AdSoyad, o.SicilNo
        FROM Operatorler o JOIN Kullanicilar k ON k.Id = o.KullaniciId
        WHERE o.Id = :id
    """), {"id": operator_id}).fetchone()
    if not op:
        from fastapi import HTTPException
        raise HTTPException(404, "Operatör bulunamadı")

    yil_filtre = f"AND YEAR(mie.BitisZamani) = {yil}" if yil else ""

    # Özet
    ozet = db.execute(text(f"""
        SELECT
            COUNT(DISTINCT mie.Id),
            MIN(mie.BaslangicZamani),
            MAX(mie.BitisZamani)
        FROM MakineIsEmirleri mie
        WHERE mie.OperatorId = :oid AND mie.Durum = 'tamamlandi'
        {yil_filtre}
    """), {"oid": operator_id}).fetchone()

    # Ortalama kabul süresi
    kabul_row = db.execute(text(f"""
        SELECT AVG(KabulDk) FROM (
            SELECT DATEDIFF(MINUTE, mie.OlusturmaTarihi,
                (SELECT TOP 1 ul.Zaman FROM UretimLoglari ul
                 WHERE ul.MakineIsEmriId = mie.Id AND ul.IslemTipi = 'is_emri_kabul'
                 ORDER BY ul.Zaman)) AS KabulDk
            FROM MakineIsEmirleri mie
            WHERE mie.OperatorId = :oid AND mie.Durum = 'tamamlandi'
            {yil_filtre}
        ) AS t WHERE KabulDk IS NOT NULL
    """), {"oid": operator_id}).fetchone()

    # Kalite
    kal = db.execute(text(f"""
        SELECT SUM(kk.UretilenAdet), SUM(kk.KabulAdet)
        FROM KaliteKontrol kk
        JOIN MakineIsEmirleri mie ON mie.Id = kk.MakineIsEmriId
        WHERE kk.OperatorId = :oid
        {yil_filtre}
    """), {"oid": operator_id}).fetchone()
    kalite_oran = round(kal[1] / kal[0] * 100, 1) if kal and kal[0] else None

    # Aylık trend
    aylik_rows = db.execute(text(f"""
        SELECT Yil, Ay, COUNT(*) AS TamamlananIs, AVG(KabulDk) AS OrtKabul
        FROM (
            SELECT
                YEAR(mie.BitisZamani) AS Yil,
                MONTH(mie.BitisZamani) AS Ay,
                DATEDIFF(MINUTE, mie.OlusturmaTarihi,
                    (SELECT TOP 1 ul.Zaman FROM UretimLoglari ul
                     WHERE ul.MakineIsEmriId = mie.Id AND ul.IslemTipi = 'is_emri_kabul'
                     ORDER BY ul.Zaman)) AS KabulDk
            FROM MakineIsEmirleri mie
            WHERE mie.OperatorId = :oid AND mie.Durum = 'tamamlandi'
            AND mie.BitisZamani IS NOT NULL
            {yil_filtre}
        ) AS t
        GROUP BY Yil, Ay
        ORDER BY Yil, Ay
    """), {"oid": operator_id}).fetchall()

    # Aylık kalite
    aylik_kal = db.execute(text(f"""
        SELECT YEAR(mie.BitisZamani), MONTH(mie.BitisZamani),
               SUM(kk.UretilenAdet), SUM(kk.KabulAdet)
        FROM KaliteKontrol kk
        JOIN MakineIsEmirleri mie ON mie.Id = kk.MakineIsEmriId
        WHERE kk.OperatorId = :oid AND mie.BitisZamani IS NOT NULL
        {yil_filtre}
        GROUP BY YEAR(mie.BitisZamani), MONTH(mie.BitisZamani)
    """), {"oid": operator_id}).fetchall()
    kal_map = {(r[0], r[1]): (r[2], r[3]) for r in aylik_kal}

    aylik = []
    for r in aylik_rows:
        yil_v, ay_v = r[0], r[1]
        k = kal_map.get((yil_v, ay_v))
        kal_ay = round(k[1] / k[0] * 100, 1) if k and k[0] else None
        ort_kabul = float(r[3]) if r[3] else None

        # Basit skor
        skor = None
        if r[2] > 0:
            p = 0.0
            if ort_kabul is not None:
                p += 30 if ort_kabul <= 2 else 25 if ort_kabul <= 5 else 18 if ort_kabul <= 15 else 10
            else:
                p += 30
            p += (kal_ay / 100 * 35) if kal_ay else 35
            p += 35  # arıza ve başlatma için varsayılan
            skor = round(min(100, p), 1)

        aylik.append(OperatorAylikOut(
            yil=yil_v, ay=ay_v,
            ay_adi=f"{AY_ADLARI[ay_v]} {yil_v}",
            tamamlanan_is=int(r[2] or 0),
            ort_kabul_suresi_dk=ort_kabul,
            kalite_orani=kal_ay,
            verimlilik_skoru=skor,
        ))

    return OperatorGecmisOut(
        operator_id=op[0], ad_soyad=op[1], sicil_no=op[2],
        toplam_is=int(ozet[0] or 0),
        ort_kabul_suresi_dk=float(kabul_row[0]) if kabul_row and kabul_row[0] else None,
        kalite_orani=kalite_oran,
        ilk_is=ozet[1],
        son_is=ozet[2],
        aylik=aylik,
    )


@router.get("/ozet")
def gecmis_ozet(
    db: Session = Depends(get_db),
    _: Kullanici = Depends(get_current_user),
):
    """Dashboard için hızlı özet."""
    bu_yil = datetime.now().year

    toplam = db.execute(text("""
        SELECT COUNT(*) FROM IsEmirleri WHERE Durum = 'tamamlandi'
    """)).scalar()

    bu_yil_toplam = db.execute(text("""
        SELECT COUNT(*) FROM IsEmirleri
        WHERE Durum = 'tamamlandi' AND YEAR(OlusturmaTarihi) = :y
    """), {"y": bu_yil}).scalar()

    urun_cesidi = db.execute(text("""
        SELECT COUNT(DISTINCT StokId) FROM IsEmirleri WHERE Durum = 'tamamlandi'
    """)).scalar()

    return {
        "toplam_uretim": int(toplam or 0),
        "bu_yil_uretim": int(bu_yil_toplam or 0),
        "urun_cesidi": int(urun_cesidi or 0),
        "yil": bu_yil,
    }