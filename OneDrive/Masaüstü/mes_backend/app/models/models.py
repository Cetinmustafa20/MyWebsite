"""
SQLAlchemy ORM modelleri — mes_schema.sql ile birebir eşleşir.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    ForeignKey, Text, Computed, Numeric,
)
from sqlalchemy.orm import relationship
from app.db.database import Base


class Kullanici(Base):
    __tablename__ = "Kullanicilar"

    id               = Column("Id", Integer, primary_key=True, index=True)
    ad_soyad         = Column("AdSoyad", String(100), nullable=False)
    kullanici_adi    = Column("KullaniciAdi", String(50), unique=True, nullable=False)
    sifre_hash       = Column("SifreHash", String(255), nullable=False)
    rol              = Column("Rol", String(20), nullable=False, default="operator")
    aktif            = Column("Aktif", Boolean, nullable=False, default=True)
    olusturma_tarihi = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)
    guncelleme_tarihi = Column("GuncellemeTarihi", DateTime, nullable=True)

    operator = relationship("Operator", back_populates="kullanici", uselist=False)


class Operator(Base):
    __tablename__ = "Operatorler"

    id               = Column("Id", Integer, primary_key=True, index=True)
    kullanici_id     = Column("KullaniciId", Integer, ForeignKey("Kullanicilar.Id"), nullable=False)
    sicil_no         = Column("SicilNo", String(30), unique=True, nullable=False)
    departman        = Column("Departman", String(100), nullable=True)
    aktif            = Column("Aktif", Boolean, nullable=False, default=True)
    olusturma_tarihi = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)

    kullanici          = relationship("Kullanici", back_populates="operator")
    makine_is_emirleri = relationship("MakineIsEmri", back_populates="operator")
    arizalar           = relationship("Ariza", back_populates="operator")
    makine_yetkileri   = relationship("OperatorMakineYetki", back_populates="operator")


class Makine(Base):
    __tablename__ = "Makineler"

    id                = Column("Id", Integer, primary_key=True, index=True)
    kod               = Column("Kod", String(20), unique=True, nullable=False)
    ad                = Column("Ad", String(100), nullable=False)
    aciklama          = Column("Aciklama", String(500), nullable=True)
    durum             = Column("Durum", String(20), nullable=False, default="bosta")
    birim_sure_saniye = Column("BirimSureSaniye", Integer, nullable=True)
    aktif             = Column("Aktif", Boolean, nullable=False, default=True)
    olusturma_tarihi  = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)
    guncelleme_tarihi = Column("GuncellemeTarihi", DateTime, nullable=True)

    makine_is_emirleri = relationship("MakineIsEmri", back_populates="makine")
    arizalar           = relationship("Ariza", back_populates="makine")
    uretim_loglari     = relationship("UretimLog", back_populates="makine")
    tablet_kayitlari   = relationship("TabletKaydi", back_populates="makine")
    operator_yetkileri = relationship("OperatorMakineYetki", back_populates="makine")


class StokKarti(Base):
    __tablename__ = "StokKartlari"

    id               = Column("Id", Integer, primary_key=True, index=True)
    stok_kodu        = Column("StokKodu", String(50), unique=True, nullable=False)
    stok_adi         = Column("StokAdi", String(200), nullable=False)
    birim            = Column("Birim", String(20), nullable=False, default="ADET")
    kategori         = Column("Kategori", String(100), nullable=True)
    aciklama         = Column("Aciklama", String(500), nullable=True)
    urun_tipi        = Column("UrunTipi", String(20), nullable=False, default="hammadde")
    birim_agirlik    = Column("BirimAgirlik", Numeric(10, 3), nullable=True)
    en               = Column("En", Numeric(10, 2), nullable=True)
    boy              = Column("Boy", Numeric(10, 2), nullable=True)
    kalinlik         = Column("Kalinlik", Numeric(10, 2), nullable=True)
    min_stok         = Column("MinStok", Integer, nullable=True)
    notlar           = Column("Notlar", String(1000), nullable=True)
    aktif            = Column("Aktif", Boolean, nullable=False, default=True)
    olusturma_tarihi = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)

    is_emirleri = relationship("IsEmri", back_populates="stok")


class Cari(Base):
    __tablename__ = "Cariler"

    id               = Column("Id", Integer, primary_key=True, index=True)
    cari_kodu        = Column("CariKodu", String(30), unique=True, nullable=False)
    unvan            = Column("Unvan", String(200), nullable=False)
    cari_tipi        = Column("CariTipi", String(20), nullable=False, default="musteri")
    vergi_no         = Column("VergiNo", String(20), nullable=True)
    vergi_dairesi    = Column("VergiDairesi", String(100), nullable=True)
    telefon          = Column("Telefon", String(30), nullable=True)
    adres            = Column("Adres", String(500), nullable=True)
    aktif            = Column("Aktif", Boolean, nullable=False, default=True)
    olusturma_tarihi = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)

    is_emirleri = relationship("IsEmri", back_populates="cari")


class IsEmri(Base):
    __tablename__ = "IsEmirleri"

    id                   = Column("Id", Integer, primary_key=True, index=True)
    is_emri_no           = Column("IsEmriNo", String(30), unique=True, nullable=False)
    stok_id              = Column("StokId", Integer, ForeignKey("StokKartlari.Id"), nullable=False)
    cari_id              = Column("CariId", Integer, ForeignKey("Cariler.Id"), nullable=True)
    miktar               = Column("Miktar", Integer, nullable=False)
    durum                = Column("Durum", String(20), nullable=False, default="bekliyor")
    planlanan_baslangic  = Column("PlanlananBaslangic", DateTime, nullable=True)
    planlanan_bitis      = Column("PlanlananBitis", DateTime, nullable=True)
    gercek_baslangic     = Column("GercekBaslangic", DateTime, nullable=True)
    gercek_bitis         = Column("GercekBitis", DateTime, nullable=True)
    notlar               = Column("Notlar", String(1000), nullable=True)
    olusturan_id         = Column("OlusturanId", Integer, ForeignKey("Kullanicilar.Id"), nullable=True)
    olusturma_tarihi     = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)
    guncelleme_tarihi    = Column("GuncellemeTarihi", DateTime, nullable=True)

    stok               = relationship("StokKarti", back_populates="is_emirleri")
    cari               = relationship("Cari", back_populates="is_emirleri")
    makine_is_emirleri = relationship("MakineIsEmri", back_populates="is_emri")


class MakineIsEmri(Base):
    __tablename__ = "MakineIsEmirleri"

    id               = Column("Id", Integer, primary_key=True, index=True)
    is_emri_id       = Column("IsEmriId", Integer, ForeignKey("IsEmirleri.Id"), nullable=False)
    makine_id        = Column("MakineId", Integer, ForeignKey("Makineler.Id"), nullable=False)
    operator_id      = Column("OperatorId", Integer, ForeignKey("Operatorler.Id"), nullable=True)
    sira_no          = Column("SiraNo", Integer, nullable=False, default=1)
    durum            = Column("Durum", String(20), nullable=False, default="bekliyor")
    baslangic_zamani = Column("BaslangicZamani", DateTime, nullable=True)
    bitis_zamani     = Column("BitisZamani", DateTime, nullable=True)
    notlar           = Column("Notlar", String(500), nullable=True)
    olusturma_tarihi = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)
    guncelleme_tarihi = Column("GuncellemeTarihi", DateTime, nullable=True)

    is_emri        = relationship("IsEmri", back_populates="makine_is_emirleri")
    makine         = relationship("Makine", back_populates="makine_is_emirleri")
    operator       = relationship("Operator", back_populates="makine_is_emirleri")
    uretim_loglari = relationship("UretimLog", back_populates="makine_is_emri")


class UretimLog(Base):
    __tablename__ = "UretimLoglari"

    id                = Column("Id", Integer, primary_key=True, index=True)
    makine_is_emri_id = Column("MakineIsEmriId", Integer, ForeignKey("MakineIsEmirleri.Id"), nullable=False)
    islem_tipi        = Column("IslemTipi", String(30), nullable=False)
    zaman             = Column("Zaman", DateTime, default=datetime.utcnow)
    aciklama          = Column("Aciklama", String(500), nullable=True)
    operator_id       = Column("OperatorId", Integer, ForeignKey("Operatorler.Id"), nullable=True)
    makine_id         = Column("MakineId", Integer, ForeignKey("Makineler.Id"), nullable=False)
    onceki_durum      = Column("OncekiDurum", String(20), nullable=True)
    yeni_durum        = Column("YeniDurum", String(20), nullable=True)

    makine_is_emri = relationship("MakineIsEmri", back_populates="uretim_loglari")
    makine         = relationship("Makine", back_populates="uretim_loglari")


class Ariza(Base):
    __tablename__ = "Arizalar"

    id               = Column("Id", Integer, primary_key=True, index=True)
    makine_id        = Column("MakineId", Integer, ForeignKey("Makineler.Id"), nullable=False)
    operator_id      = Column("OperatorId", Integer, ForeignKey("Operatorler.Id"), nullable=False)
    ariza_tipi       = Column("ArizaTipi", String(50), nullable=False)
    aciklama         = Column("Aciklama", String(1000), nullable=True)
    baslangic        = Column("Baslangic", DateTime, default=datetime.utcnow)
    bitis            = Column("Bitis", DateTime, nullable=True)
    durum            = Column("Durum", String(20), nullable=False, default="devam_ediyor")
    cozum_aciklamasi = Column("CozumAciklamasi", String(1000), nullable=True)
    olusturma_tarihi = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)

    makine   = relationship("Makine", back_populates="arizalar")
    operator = relationship("Operator", back_populates="arizalar")


class KaliteKontrol(Base):
    __tablename__ = "KaliteKontrol"

    id                = Column("Id", Integer, primary_key=True, index=True)
    makine_is_emri_id = Column("MakineIsEmriId", Integer, ForeignKey("MakineIsEmirleri.Id"), nullable=False)
    makine_id         = Column("MakineId", Integer, ForeignKey("Makineler.Id"), nullable=False)
    operator_id       = Column("OperatorId", Integer, ForeignKey("Operatorler.Id"), nullable=False)
    kontrol_zamani    = Column("KontrolZamani", DateTime, default=datetime.utcnow)
    uretilen_adet     = Column("UretilenAdet", Integer, nullable=False, default=0)
    kabul_adet        = Column("KabulAdet", Integer, nullable=False, default=0)
    red_adet          = Column("RedAdet", Integer, nullable=False, default=0)
    fire_adet         = Column("FireAdet", Integer, nullable=False, default=0)
    ret_nedeni        = Column("RetNedeni", String(200), nullable=True)
    aciklama          = Column("Aciklama", String(500), nullable=True)
    olusturma_tarihi  = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)

    makine_is_emri = relationship("MakineIsEmri", backref="kalite_kontroller")
    makine         = relationship("Makine", backref="kalite_kontroller")
    operator       = relationship("Operator", backref="kalite_kontroller")


class BakimPlani(Base):
    __tablename__ = "BakimPlanlari"

    id               = Column("Id", Integer, primary_key=True, index=True)
    makine_id        = Column("MakineId", Integer, ForeignKey("Makineler.Id"), nullable=False)
    bakim_adi        = Column("BakimAdi", String(200), nullable=False)
    bakim_tipi       = Column("BakimTipi", String(50), nullable=False, default="periyodik")
    peryot_gun       = Column("PeryotGun", Integer, nullable=False, default=30)
    son_bakim_tarihi = Column("SonBakimTarihi", DateTime, nullable=True)
    sonraki_bakim    = Column("SonrakiBakim", DateTime, nullable=True)
    sorumlu_id       = Column("SorumluId", Integer, ForeignKey("Operatorler.Id"), nullable=True)
    aciklama         = Column("Aciklama", String(500), nullable=True)
    aktif            = Column("Aktif", Boolean, nullable=False, default=True)
    olusturma_tarihi = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)

    makine   = relationship("Makine", backref="bakim_planlari")
    sorumlu  = relationship("Operator", backref="bakim_planlari", foreign_keys=[sorumlu_id])
    kayitlar = relationship("BakimKaydi", back_populates="plan")


class BakimKaydi(Base):
    __tablename__ = "BakimKayitlari"

    id               = Column("Id", Integer, primary_key=True, index=True)
    bakim_plan_id    = Column("BakimPlanId", Integer, ForeignKey("BakimPlanlari.Id"), nullable=False)
    makine_id        = Column("MakineId", Integer, ForeignKey("Makineler.Id"), nullable=False)
    yapan_id         = Column("YapanId", Integer, ForeignKey("Operatorler.Id"), nullable=False)
    baslangic_zamani = Column("BaslangicZamani", DateTime, default=datetime.utcnow)
    bitis_zamani     = Column("BitisZamani", DateTime, nullable=True)
    notlar           = Column("Notlar", String(1000), nullable=True)
    durum            = Column("Durum", String(20), nullable=False, default="tamamlandi")
    olusturma_tarihi = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)

    plan   = relationship("BakimPlani", back_populates="kayitlar")
    makine = relationship("Makine", backref="bakim_kayitlari")
    yapan  = relationship("Operator", backref="bakim_kayitlari", foreign_keys=[yapan_id])


class TakimTalebi(Base):
    __tablename__ = "TakimTalepleri"

    id               = Column("Id", Integer, primary_key=True, index=True)
    makine_id        = Column("MakineId", Integer, ForeignKey("Makineler.Id"), nullable=False)
    operator_id      = Column("OperatorId", Integer, ForeignKey("Operatorler.Id"), nullable=False)
    talep_tipi       = Column("TalepTipi", String(30), nullable=False)
    aciklama         = Column("Aciklama", String(1000), nullable=False)
    oncelik          = Column("Oncelik", String(20), nullable=False, default="normal")
    durum            = Column("Durum", String(20), nullable=False, default="bekliyor")
    cevap_aciklamasi = Column("CevapAciklamasi", String(1000), nullable=True)
    cevap_veren_id   = Column("CevapVerenId", Integer, ForeignKey("Kullanicilar.Id"), nullable=True)
    cevap_zamani     = Column("CevapZamani", DateTime, nullable=True)
    olusturma_tarihi = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)

    makine   = relationship("Makine", backref="takim_talepleri")
    operator = relationship("Operator", backref="takim_talepleri")


class UretimSayaci(Base):
    __tablename__ = "UretimSayaci"

    id                = Column("Id", Integer, primary_key=True, index=True)
    makine_is_emri_id = Column("MakineIsEmriId", Integer, ForeignKey("MakineIsEmirleri.Id"), nullable=False)
    makine_id         = Column("MakineId", Integer, ForeignKey("Makineler.Id"), nullable=False)
    operator_id       = Column("OperatorId", Integer, ForeignKey("Operatorler.Id"), nullable=False)
    uretilen_adet     = Column("UretilenAdet", Integer, nullable=False, default=0)
    kayit_zamani      = Column("KayitZamani", DateTime, default=datetime.utcnow)

    makine_is_emri = relationship("MakineIsEmri", backref="sayac_kayitlari")
    makine         = relationship("Makine", backref="sayac_kayitlari")
    operator       = relationship("Operator", backref="sayac_kayitlari")


class TabletKaydi(Base):
    __tablename__ = "TabletKayitlari"

    id               = Column("Id", Integer, primary_key=True, index=True)
    tablet_id        = Column("TabletId", String(50), unique=True, nullable=False)
    makine_id        = Column("MakineId", Integer, ForeignKey("Makineler.Id"), nullable=False)
    tablet_adi       = Column("TabletAdi", String(100), nullable=True)
    son_aktivite     = Column("SonAktivite", DateTime, nullable=True)
    aktif            = Column("Aktif", Boolean, nullable=False, default=True)
    olusturma_tarihi = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)

    makine = relationship("Makine", back_populates="tablet_kayitlari")


class OperatorMakineYetki(Base):
    __tablename__ = "OperatorMakineYetkileri"

    id               = Column("Id", Integer, primary_key=True, index=True)
    operator_id      = Column("OperatorId", Integer, ForeignKey("Operatorler.Id"), nullable=False)
    makine_id        = Column("MakineId", Integer, ForeignKey("Makineler.Id"), nullable=False)
    aktif            = Column("Aktif", Boolean, nullable=False, default=True)
    olusturma_tarihi = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)

    operator = relationship("Operator", back_populates="makine_yetkileri")
    makine   = relationship("Makine", back_populates="operator_yetkileri")


class UretimPartisi(Base):
    __tablename__ = "UretimPartileri"

    id                = Column("Id", Integer, primary_key=True, index=True)
    parti_kodu        = Column("PartiKodu", String(50), unique=True, nullable=False)
    makine_is_emri_id = Column("MakineIsEmriId", Integer, ForeignKey("MakineIsEmirleri.Id"), nullable=False)
    makine_id         = Column("MakineId", Integer, ForeignKey("Makineler.Id"), nullable=False)
    operator_id       = Column("OperatorId", Integer, ForeignKey("Operatorler.Id"), nullable=False)
    stok_id           = Column("StokId", Integer, ForeignKey("StokKartlari.Id"), nullable=False)
    is_emri_no        = Column("IsEmriNo", String(30), nullable=False)
    uretilen_adet     = Column("UretilenAdet", Integer, nullable=False, default=0)
    kabul_adet        = Column("KabulAdet", Integer, nullable=False, default=0)
    fire_adet         = Column("FireAdet", Integer, nullable=False, default=0)
    baslangic_zamani  = Column("BaslangicZamani", DateTime, nullable=False)
    bitis_zamani      = Column("BitisZamani", DateTime, default=datetime.utcnow)
    qr_icerik         = Column("QrIcerik", String(500), nullable=False)
    notlar            = Column("Notlar", String(1000), nullable=True)
    olusturma_tarihi  = Column("OlusturmaTarihi", DateTime, default=datetime.utcnow)

    makine_is_emri = relationship("MakineIsEmri", backref="partiler")
    makine         = relationship("Makine", backref="partiler")
    operator       = relationship("Operator", backref="partiler")
    stok           = relationship("StokKarti", backref="partiler")
