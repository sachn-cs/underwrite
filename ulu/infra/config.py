"""Application configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration for the middleware."""

    database_url: str = ""
    algod_token: str = ""
    algod_url: str = "http://localhost:4001"
    app_env: str = "development"
    log_level: str = "INFO"
    dlg_cap_ratio: float = 0.05
    npa_trigger_days: int = 120
    collateral_min_ratio: float = 0.05
    jwt_secret: str = "change-me-in-production-32byte-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
