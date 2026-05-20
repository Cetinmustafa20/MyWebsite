"""
Audit Log Servisi.
Kim, ne zaman, ne yapti - hepsini kaydeder.
"""
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session


def audit_log_ekle(
    db: Session,
    islem: str,
    detay: str = None,
    kullanici_id: int = None,
    kullanici_adi: str = None,
    rol: str = None,
    ip_adresi: str = None,
    basarili: bool = True,
):
    try:
        db.execute(
            text(
                """INSERT INTO AuditLog
                   (KullaniciId, KullaniciAdi, Rol, Islem, Detay, IpAdresi, Zaman, Basarili)
                   VALUES (:kid, :kadi, :rol, :islem, :detay, :ip, :zaman, :basarili)"""
            ),
            {
                "kid": kullanici_id,
                "kadi": kullanici_adi,
                "rol": rol,
                "islem": islem,
                "detay": detay,
                "ip": ip_adresi,
                "zaman": datetime.utcnow(),
                "basarili": 1 if basarili else 0,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
