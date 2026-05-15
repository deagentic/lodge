from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://appuser:changeme@localhost:5432/lodge_db"
    app_title: str = "Lodge"
    app_version: str = "1.0.0"

    # HTTP Basic Auth for dashboard (F7 — ADR-0007)
    # Set to empty string to disable auth (not recommended outside local dev)
    dashboard_username: str = ""
    dashboard_password: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
