from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import redis
from app.core.config import settings

# SQL Server bağlantısı
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,       # bağlantı kopuksa yeniden bağlan
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,      # DEBUG=true ise SQL logla
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency injection için DB session üretici."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Redis bağlantısı — anlık makine durumları buraya yazılır
redis_client = redis.from_url(
    settings.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    socket_connect_timeout=3,
    socket_timeout=3,
)

def get_redis() -> redis.Redis:
    return redis_client
