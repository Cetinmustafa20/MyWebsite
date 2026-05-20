"""
Maliyet Analizi Endpoint'leri
- Stok kartına birim maliyet tanımla
- BOM'dan iş emri başına maliyet hesapla
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.db.database import get_db
from app.models.models import Kullanici
from app.core.security import get_current_user, require_yonetici

router = APIRouter(prefix="/maliyet", tags=["maliyet"])

class StokFiyatGuncelle(BaseModel):
    birim_maliyet: Optional[float] = None
    para_birimi: str = "TRY"

class StokMaliyetOut(BaseModel):
    id: int
    stok_kodu: str
    stok_adi: str
    birim: str
    urun_tipi: str
    birim_maliyet: Optional[float]
    para_birimi: str

class BomMaliyetKalem(BaseModel):
    asama_no: int
    asama_adi: str
    malzeme_adi: str
    malzeme_kodu: str
    miktar: float
    birim: str
    fire_yuzdesi: float
    birim_maliyet: Optional[float]
    toplam_maliyet: Optional[float]
    para_birimi: str

class BomMaliyetOut(BaseModel):
    bom_id: int
    urun_kodu: str
    urun_adi: str
    versiyon: str
    kalemler: List[BomMaliyetKalem]
    toplam_malzeme_maliyeti: Optional[float]
    toplam_iscilik_saati: Optional[float]
    para_birimi: str
    fiyatsiz_kalem_sayisi: int

class IsEmriMaliyetOut(BaseModel):
    is_emri_no: str
    stok_adi: str
    miktar: int
    toplam_malzeme_maliyeti: Optional[float]
    birim_malzeme_maliyeti: Optional[float]
    toplam_iscilik_saati: Optional[float]
    fiyatsiz_kalem_sayisi: int
    para_birimi: str
    durum: str
    olusturma_tarihi: datetime


@router.get("/stok-fiyatlar", response_model=List[StokMaliyetOut])
def stok_fiyat_listesi(db: Session = Depends(get_db), _: Kullanici = Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT Id, StokKodu, StokAdi, Birim,
               ISNULL(UrunTipi,'hammadde'), BirimMaliyet, ISNULL(ParaBirimi,'TRY')
        FROM StokKartlari WHERE Aktif=1 ORDER BY StokKodu
    """)).fetchall()
    return [StokMaliyetOut(id=r[0],stok_kodu=r[1],stok_adi=r[2],birim=r[3],
            urun_tipi=r[4],birim_maliyet=float(r[5]) if r[5] else None,para_birimi=r[6])
            for r in rows]


@router.patch("/stok/{stok_id}/fiyat")
def stok_fiyat_guncelle(stok_id:int, body:StokFiyatGuncelle,
    db:Session=Depends(get_db), _:Kullanici=Depends(require_yonetici)):
    if not db.execute(text("SELECT Id FROM StokKartlari WHERE Id=:id"),{"id":stok_id}).fetchone():
        raise HTTPException(404,"Stok kartı bulunamadı")
    db.execute(text("UPDATE StokKartlari SET BirimMaliyet=:bm, ParaBirimi=:pb WHERE Id=:id"),
               {"bm":body.birim_maliyet,"pb":body.para_birimi,"id":stok_id})
    db.commit()
    return {"detail":"Fiyat güncellendi"}


@router.get("/bom/{bom_id}", response_model=BomMaliyetOut)
def bom_maliyet(bom_id:int, uretim_miktari:int=1,
    db:Session=Depends(get_db), _:Kullanici=Depends(get_current_user)):
    bom = db.execute(text("""
        SELECT b.Id,s.StokKodu,s.StokAdi,b.Versiyon,ISNULL(s.ParaBirimi,'TRY')
        FROM BomBasliklar b JOIN StokKartlari s ON s.Id=b.UrunStokId
        WHERE b.Id=:id AND b.Aktif=1
    """),{"id":bom_id}).fetchone()
    if not bom: raise HTTPException(404,"BOM bulunamadı")

    rows = db.execute(text("""
        SELECT a.AsamaNo,a.AsamaAdi,k.Miktar,k.Birim,k.FireYuzdesi,
               s.StokKodu,s.StokAdi,s.BirimMaliyet,ISNULL(s.ParaBirimi,'TRY')
        FROM BomAsamalar a JOIN BomKalemler k ON k.BomAsamaId=a.Id
        JOIN StokKartlari s ON s.Id=k.MalzemeStokId
        WHERE a.BomId=:bid ORDER BY a.AsamaNo
    """),{"bid":bom_id}).fetchall()

    iscilik = float(db.execute(text(
        "SELECT ISNULL(SUM(IscilkSaati),0) FROM BomAsamalar WHERE BomId=:bid"
    ),{"bid":bom_id}).scalar() or 0) * uretim_miktari

    kalemler=[]; toplam=0.0; fiyatsiz=0; tam=True
    for r in rows:
        ano,aadi,miktar,birim,fire,mkod,madi,bm,para = r
        fc=1+float(fire or 0)/100
        net=float(miktar)*uretim_miktari*fc
        tk=None
        if bm is not None: tk=round(float(bm)*net,4); toplam+=tk
        else: fiyatsiz+=1; tam=False
        kalemler.append(BomMaliyetKalem(asama_no=ano,asama_adi=aadi,malzeme_adi=madi,
            malzeme_kodu=mkod,miktar=net,birim=birim,fire_yuzdesi=float(fire or 0),
            birim_maliyet=float(bm) if bm else None,toplam_maliyet=tk,para_birimi=para))

    return BomMaliyetOut(bom_id=bom[0],urun_kodu=bom[1],urun_adi=bom[2],versiyon=bom[3],
        kalemler=kalemler,toplam_malzeme_maliyeti=round(toplam,4) if tam else None,
        toplam_iscilik_saati=iscilik if iscilik>0 else None,
        para_birimi=bom[4],fiyatsiz_kalem_sayisi=fiyatsiz)


@router.get("/is-emirleri", response_model=List[IsEmriMaliyetOut])
def is_emirleri_maliyet(durum:Optional[str]=None, limit:int=100,
    db:Session=Depends(get_db), _:Kullanici=Depends(get_current_user)):
    where="WHERE ie.Durum != 'iptal'"
    params={"lim":limit}
    if durum: where+=" AND ie.Durum=:durum"; params["durum"]=durum

    isler=db.execute(text(f"""
        SELECT ie.Id,ie.IsEmriNo,s.StokAdi,ie.Miktar,ie.Durum,ie.OlusturmaTarihi,s.Id
        FROM IsEmirleri ie JOIN StokKartlari s ON s.Id=ie.StokId
        {where} ORDER BY ie.OlusturmaTarihi DESC
        OFFSET 0 ROWS FETCH NEXT :lim ROWS ONLY
    """),params).fetchall()

    result=[]
    for ie_id,ie_no,stok_adi,miktar,d,olusturma,stok_id in isler:
        bom=db.execute(text("SELECT TOP 1 Id FROM BomBasliklar WHERE UrunStokId=:sid AND Aktif=1 ORDER BY Id DESC"),
                       {"sid":stok_id}).fetchone()
        if not bom:
            result.append(IsEmriMaliyetOut(is_emri_no=ie_no,stok_adi=stok_adi,miktar=miktar,
                toplam_malzeme_maliyeti=None,birim_malzeme_maliyeti=None,
                toplam_iscilik_saati=None,fiyatsiz_kalem_sayisi=0,
                para_birimi="TRY",durum=d,olusturma_tarihi=olusturma)); continue

        km_rows=db.execute(text("""
            SELECT k.Miktar,k.FireYuzdesi,s.BirimMaliyet
            FROM BomAsamalar a JOIN BomKalemler k ON k.BomAsamaId=a.Id
            JOIN StokKartlari s ON s.Id=k.MalzemeStokId WHERE a.BomId=:bid
        """),{"bid":bom[0]}).fetchall()

        iscilik=float(db.execute(text(
            "SELECT ISNULL(SUM(IscilkSaati),0) FROM BomAsamalar WHERE BomId=:bid"
        ),{"bid":bom[0]}).scalar() or 0)*miktar

        bm_birim=0.0; fiyatsiz=0; tam=True
        for km,fire,bm in km_rows:
            fc=1+float(fire or 0)/100
            if bm is not None: bm_birim+=float(km)*fc*float(bm)
            else: fiyatsiz+=1; tam=False

        result.append(IsEmriMaliyetOut(is_emri_no=ie_no,stok_adi=stok_adi,miktar=miktar,
            toplam_malzeme_maliyeti=round(bm_birim*miktar,2) if tam else None,
            birim_malzeme_maliyeti=round(bm_birim,4) if tam else None,
            toplam_iscilik_saati=iscilik if iscilik>0 else None,
            fiyatsiz_kalem_sayisi=fiyatsiz,para_birimi="TRY",
            durum=d,olusturma_tarihi=olusturma))
    return result


@router.get("/ozet")
def maliyet_ozet(db:Session=Depends(get_db), _:Kullanici=Depends(get_current_user)):
    f=int(db.execute(text("SELECT COUNT(*) FROM StokKartlari WHERE BirimMaliyet IS NOT NULL AND Aktif=1")).scalar() or 0)
    t=int(db.execute(text("SELECT COUNT(*) FROM StokKartlari WHERE Aktif=1")).scalar() or 0)
    return {"fiyatli_stok":f,"tum_stok":t,"fiyatsiz_stok":t-f}