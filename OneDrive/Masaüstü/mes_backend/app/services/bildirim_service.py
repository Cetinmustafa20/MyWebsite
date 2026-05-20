"""
E-posta bildirim servisi.
Arıza, talep ve gecikmiş bakım durumlarında otomatik mail gönderir.
"""
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from app.core.config import settings
import importlib
import app.core.config as _cfg
importlib.reload(_cfg)
from app.core.config import settings


def _mail_gonder(konu: str, icerik_html: str):
    from app.core.config import settings as s
    if not s.MAIL_USER or not s.MAIL_PASSWORD or not s.mail_to_list:
        print(f"[BİLDİRİM] Mail ayarları eksik: {konu}")
        return

    def gonder():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[MES] {konu}"
            msg["From"] = settings.MAIL_FROM
            msg["To"] = ", ".join(settings.mail_to_list)

            html_part = MIMEText(icerik_html, "html", "utf-8")
            msg.attach(html_part)

            with smtplib.SMTP('142.251.127.108', 587) as server:
                server.ehlo()
                server.starttls()
                server.login(settings.MAIL_USER, settings.MAIL_PASSWORD)
                server.sendmail(
                    settings.MAIL_USER,
                    settings.mail_to_list,
                    msg.as_string(),
                )
            print(f"[BİLDİRİM] Mail gönderildi: {konu}")
        except Exception as e:
            print(f"[BİLDİRİM] Mail gönderilemedi: {e}")

    gonder()


def _html_sablon(baslik: str, renk: str, satirlar: list[tuple]) -> str:
    satirlar_html = "".join(
        f"<tr><td style='padding:6px 12px;color:#6b7280;font-size:13px'>{k}</td>"
        f"<td style='padding:6px 12px;font-weight:500;font-size:13px'>{v}</td></tr>"
        for k, v in satirlar
    )
    return f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto">
      <div style="background:{renk};padding:20px 24px;border-radius:12px 12px 0 0">
        <h2 style="color:white;margin:0;font-size:18px">{baslik}</h2>
        <p style="color:rgba(255,255,255,0.8);margin:4px 0 0;font-size:13px">
          {datetime.now().strftime('%d.%m.%Y %H:%M')}
        </p>
      </div>
      <div style="background:#f9fafb;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px;padding:8px 0">
        <table style="width:100%;border-collapse:collapse">
          {satirlar_html}
        </table>
      </div>
      <p style="color:#9ca3af;font-size:11px;text-align:center;margin-top:12px">
        Bu mail MES Sistemi tarafından otomatik gönderilmiştir.
      </p>
    </div>
    """


def ariza_bildirimi_gonder(
    makine_kodu: str,
    makine_adi: str,
    ariza_tipi: str,
    aciklama: str,
    operator_adi: str,
):
    konu = f"ARIZA — {makine_kodu} {makine_adi}"
    html = _html_sablon(
        baslik=f"Arıza Bildirimi — {makine_kodu}",
        renk="#ef4444",
        satirlar=[
            ("Makine", f"{makine_kodu} — {makine_adi}"),
            ("Arıza Tipi", ariza_tipi.capitalize()),
            ("Açıklama", aciklama or "-"),
            ("Bildiren", operator_adi),
            ("Zaman", datetime.now().strftime("%d.%m.%Y %H:%M")),
        ],
    )
    _mail_gonder(konu, html)


def talep_bildirimi_gonder(
    makine_kodu: str,
    makine_adi: str,
    talep_tipi: str,
    aciklama: str,
    operator_adi: str,
    oncelik: str,
):
    oncelik_renk = {
        "acil": "#ef4444",
        "yuksek": "#f97316",
        "normal": "#3b82f6",
        "dusuk": "#6b7280",
    }.get(oncelik, "#3b82f6")

    konu = f"YENİ TALEP [{oncelik.upper()}] — {makine_kodu}"
    html = _html_sablon(
        baslik=f"Yeni Talep — {makine_kodu}",
        renk=oncelik_renk,
        satirlar=[
            ("Makine", f"{makine_kodu} — {makine_adi}"),
            ("Talep Tipi", talep_tipi.capitalize()),
            ("Öncelik", oncelik.capitalize()),
            ("Açıklama", aciklama),
            ("Gönderen", operator_adi),
            ("Zaman", datetime.now().strftime("%d.%m.%Y %H:%M")),
        ],
    )
    _mail_gonder(konu, html)


def bakim_gecikme_bildirimi_gonder(
    makine_kodu: str,
    makine_adi: str,
    bakim_adi: str,
    gecikme_gun: int,
    sorumlu_adi: str,
):
    konu = f"BAKIM GECİKMESİ — {makine_kodu} ({gecikme_gun} gün)"
    html = _html_sablon(
        baslik=f"Gecikmiş Bakım — {makine_kodu}",
        renk="#f59e0b",
        satirlar=[
            ("Makine", f"{makine_kodu} — {makine_adi}"),
            ("Bakım", bakim_adi),
            ("Gecikme", f"{gecikme_gun} gün"),
            ("Sorumlu", sorumlu_adi or "-"),
        ],
    )
    _mail_gonder(konu, html)


def uretim_tamamlandi_bildirimi_gonder(
    makine_kodu: str,
    is_emri_no: str,
    stok_adi: str,
    sure_dakika: int,
    operator_adi: str,
):
    saat = sure_dakika // 60
    dk = sure_dakika % 60
    sure_str = f"{saat}s {dk}dk" if saat > 0 else f"{dk} dk"

    konu = f"Üretim Tamamlandı — {is_emri_no}"
    html = _html_sablon(
        baslik="Üretim Tamamlandı",
        renk="#10b981",
        satirlar=[
            ("Makine", makine_kodu),
            ("İş Emri", is_emri_no),
            ("Ürün", stok_adi or "-"),
            ("Süre", sure_str),
            ("Operatör", operator_adi),
            ("Zaman", datetime.now().strftime("%d.%m.%Y %H:%M")),
        ],
    )
    _mail_gonder(konu, html)
