from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DB_SERVER: str = "localhost"
    DB_NAME: str = "MES_DB"
    DB_USER: str = "sa"
    DB_PASSWORD: str = ""
    DB_DRIVER: str = "ODBC Driver 17 for SQL Server"

    SECRET_KEY: str = "degistir-bunu-production-da"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    AUTH_COOKIE_NAME: str = "mes_access_token"
    AUTH_COOKIE_SECURE: bool = False

    REDIS_URL: str = "redis://localhost:6379"

    APP_NAME: str = "MES Sistemi"
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173"
    ENFORCE_HTTPS: bool = False
    DOCS_ENABLED: bool = False
    DEFAULT_RATE_LIMIT: str = "120/minute"

    MAIL_HOST: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    MAIL_USER: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "MES Sistemi <noreply@mes.com>"
    MAIL_TO: str = ""

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @property
    def mail_to_list(self) -> List[str]:
        return [m.strip() for m in self.MAIL_TO.split(",") if m.strip()]

    @property
    def database_url(self) -> str:
        return (
            f"mssql+pyodbc://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_SERVER}/{self.DB_NAME}"
            f"?driver={self.DB_DRIVER.replace(' ', '+')}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
