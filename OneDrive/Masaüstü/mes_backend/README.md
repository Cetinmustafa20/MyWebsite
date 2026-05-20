# MES Backend

Python + FastAPI tabanlı Manufacturing Execution System backend.

## Gereksinimler

- Python 3.11+
- SQL Server (Express yeterli) + SSMS
- Redis (Windows için: https://github.com/tporadowski/redis/releases)
- ODBC Driver 17 for SQL Server

## Kurulum

### 1. Veritabanını kur
SSMS'de `mes_schema.sql` dosyasını aç ve çalıştır.

### 2. Redis'i kur ve başlat
```
redis-server
```

### 3. `.env` dosyasını ayarla
```
cp .env.example .env
```
`.env` dosyasını aç, DB_SERVER, DB_USER, DB_PASSWORD değerlerini gir.

**Windows Auth kullanıyorsan** (şifresiz):
```
database_url içinde: ?driver=...&Trusted_Connection=yes
DB_USER ve DB_PASSWORD boş bırak
```

### 4. Başlat
```
start.bat
```
veya manuel:
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API Kullanımı

Sunucu ayaktayken tarayıcıda aç:
```
http://localhost:8000/docs
```
Tüm endpoint'leri buradan test edebilirsin.

## Endpoint Özeti

| Method | URL | Açıklama |
|--------|-----|----------|
| POST | /api/auth/token | Giriş, JWT token al |
| GET | /api/auth/me | Mevcut kullanıcı |
| GET | /api/makineler/ | Tüm makineler |
| GET | /api/makineler/durum | Anlık durum (Redis) |
| GET | /api/uretim/bekleyen/{makine_id} | Tablette bekleyen işler |
| POST | /api/uretim/kabul | İş emri kabul/red |
| POST | /api/uretim/baslat | Üretime başla |
| POST | /api/uretim/bitir | Üretimi bitir |
| POST | /api/uretim/ariza | Arıza bildir |
| GET | /api/is-emirleri/ | İş emirleri listesi |
| POST | /api/is-emirleri/ | Yeni iş emri oluştur |
| GET | /api/raporlar/operator-verimlilik | Operatör verimliliği |
| GET | /api/raporlar/makine-gecmis/{id} | Makine üretim geçmişi |
| GET | /api/raporlar/ariza-ozet | Makine arıza özeti |
| WS | /ws/makine-durum | Admin dashboard WebSocket |

## Proje Yapısı

```
mes_backend/
├── main.py                        # FastAPI uygulama giriş noktası
├── requirements.txt
├── .env.example
├── start.bat                      # Windows başlatma scripti
└── app/
    ├── api/
    │   └── endpoints/
    │       ├── auth.py            # Giriş / JWT
    │       ├── makineler.py       # Makine CRUD + anlık durum
    │       ├── uretim.py          # Tablet: başlat/bitir/arıza
    │       ├── is_emirleri.py     # İş emri yönetimi
    │       ├── raporlar.py        # Verimlilik ve geçmiş
    │       └── websocket.py       # Admin dashboard WS
    ├── core/
    │   ├── config.py              # Ayarlar (.env okur)
    │   └── security.py            # JWT, hash, yetkilendirme
    ├── db/
    │   └── database.py            # SQLAlchemy + Redis bağlantısı
    ├── models/
    │   └── models.py              # ORM modelleri
    └── services/
        └── makine_service.py      # Üretim iş mantığı + Redis sync
```

## Notlar

- `SureDakika` kolonları SQL Server'da `PERSISTED COMPUTED` — ORM'den yazılmaz, otomatik hesaplanır.
- Redis yoksa `/api/makineler/durum` boş döner ama sistem çalışmaya devam eder.
- `DEBUG=true` iken tüm SQL sorguları konsola yazdırılır.
