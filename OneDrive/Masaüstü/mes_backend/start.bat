@echo off
echo MES Backend baslatiliyor...

REM Sanal ortam yoksa oluştur
if not exist "venv" (
    echo Sanal ortam olusturuluyor...
    python -m venv venv
)

REM Aktifleştir
call venv\Scripts\activate

REM Paketleri kur
pip install -r requirements.txt --quiet

REM .env yoksa örnekten kopyala
if not exist ".env" (
    copy .env.example .env
    echo .env dosyasi olusturuldu - lutfen duzenleyin!
    pause
    exit
)

REM Başlat
echo Sunucu basliyor: http://localhost:8000
echo API Dokumani:    http://localhost:8000/docs
echo Durdurmak icin: CTRL+C
echo.
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
