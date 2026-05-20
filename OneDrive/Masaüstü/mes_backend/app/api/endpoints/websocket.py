"""
WebSocket endpoint.
Admin dashboard bu baglantiyi acik tutar.
Her makine durumu degistiginde tum bagli ekranlar guncellenir.
"""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.makine_service import get_tum_makine_durumlari
from app.core.config import settings
from app.core.security import decode_token
from app.db.database import SessionLocal
from app.models.models import Kullanici

router = APIRouter(tags=["websocket"])

connected_clients: list[WebSocket] = []


def _cookie_token(websocket: WebSocket):
    return websocket.cookies.get(settings.AUTH_COOKIE_NAME)


def _authenticate_dashboard_socket(websocket: WebSocket) -> bool:
    token = _cookie_token(websocket)
    if not token:
        return False

    db = SessionLocal()
    try:
        payload = decode_token(token)
        kullanici_id = payload.get("sub")
        if not kullanici_id:
            return False

        kullanici = db.query(Kullanici).filter(
            Kullanici.id == int(kullanici_id),
            Kullanici.aktif == True,
        ).first()
        if not kullanici or kullanici.rol not in {"admin", "yonetici", "operator"}:
            return False
        return True
    except Exception:
        return False
    finally:
        db.close()


async def broadcast(message: dict):
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.remove(ws)


@router.websocket("/ws/makine-durum")
async def makine_durum_ws(websocket: WebSocket):
    if not _authenticate_dashboard_socket(websocket):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    connected_clients.append(websocket)

    try:
        durumlar = get_tum_makine_durumlari()
        await websocket.send_json({"tip": "tam_liste", "veri": durumlar})

        while True:
            await asyncio.sleep(3)
            durumlar = get_tum_makine_durumlari()
            await websocket.send_json({"tip": "tam_liste", "veri": durumlar})

    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
    except Exception:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


async def notify_makine_degisim(makine_id: int, yeni_durum: dict):
    await broadcast({
        "tip": "makine_guncellendi",
        "makine_id": makine_id,
        "veri": yeni_durum,
    })