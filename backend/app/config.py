from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PGDCT_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./data/pgdct.db"
    log_level: str = "INFO"
    http_timeout_sec: float = 10.0
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
