from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "local-dev-only-secret-never-used-in-a-deployment-0001"
DEV_DEMO_PASSWORD = "Unio@Demo2026"
MIN_SECRET_BYTES = 32


class Settings(BaseSettings):
    """Environment-driven settings. Names match docs/DEPLOYMENT.md."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "unio"
    jwt_secret: str = ""
    jwt_ttl_minutes: int = 480
    cors_allowed_origins: str = "http://localhost:5173"
    campus_id: str = "CAMPUS-1"
    demo_mode_enabled: bool = False
    demo_user_password: str = ""
    login_max_failures: int = 5
    login_failure_window_seconds: int = 900
    outbox_enabled: bool = True
    outbox_poll_seconds: float = 5.0
    outbox_max_attempts: int = 5
    api_docs_enabled: bool = True

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        if not self.jwt_secret:
            if self.app_env != "dev":
                raise ValueError("JWT_SECRET must be set outside the dev environment")
            self.jwt_secret = DEV_JWT_SECRET
        if len(self.jwt_secret.encode("utf-8")) < MIN_SECRET_BYTES:
            raise ValueError("JWT_SECRET must be at least 32 bytes long")
        if self.demo_mode_enabled and not self.demo_user_password and self.app_env == "dev":
            self.demo_user_password = DEV_DEMO_PASSWORD
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
