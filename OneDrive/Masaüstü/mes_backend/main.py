from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.config import settings
from app.api.endpoints import auth, makineler, uretim, is_emirleri, raporlar, websocket, tanimlar, bom, stok_hareket, operator_performans, maliyet, vardiya, gecmis, fire
from app.db.database import SessionLocal
from app.models.models import Makine
from app.services.makine_service import _redis_makine_guncelle

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.DEFAULT_RATE_LIMIT])


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        tum_makineler = db.query(Makine).filter(Makine.aktif == True).all()
        for makine in tum_makineler:
            _redis_makine_guncelle(db, makine.id)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG or settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DEBUG or settings.DOCS_ENABLED else None,
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if settings.ENFORCE_HTTPS:
        host = request.url.hostname or ""
        is_local = host in {"localhost", "127.0.0.1"}
        forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if not is_local and forwarded_proto != "https":
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(str(https_url), status_code=307)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    if settings.ENFORCE_HTTPS:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.include_router(auth.router,         prefix="/api")
app.include_router(makineler.router,    prefix="/api")
app.include_router(uretim.router,       prefix="/api")
app.include_router(is_emirleri.router,  prefix="/api")
app.include_router(raporlar.router,     prefix="/api")
app.include_router(websocket.router)
app.include_router(tanimlar.router,     prefix="/api")
app.include_router(bom.router,               prefix="/api")
app.include_router(stok_hareket.router,      prefix="/api")
app.include_router(operator_performans.router, prefix="/api")
app.include_router(maliyet.router,           prefix="/api")
app.include_router(vardiya.router,           prefix="/api")
app.include_router(gecmis.router,            prefix="/api")
app.include_router(fire.router,              prefix="/api")


@app.get("/")
def root():
    return {"mesaj": f"{settings.APP_NAME} çalışıyor"}


@app.get("/health")
def health():
    return {"status": "ok"}