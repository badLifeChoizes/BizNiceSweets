"""
Backend configuration via pydantic-settings.

Reads from environment variables and an optional .env file.
The DB password is typed as SecretStr to prevent it from appearing in
repr/logs (T-01-01 mitigation).
"""
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database connection
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "biznice"
    postgres_user: str = "app"
    # No default — operator must supply POSTGRES_PASSWORD in env / .env
    postgres_password: SecretStr

    # Frontend static assets directory (served by backend in production, D-08)
    static_dir: str = "frontend/dist"

    # Set to True in the dev compose overlay to enable uvicorn --reload (D-11)
    uvicorn_reload: bool = False

    @property
    def database_url(self) -> str:
        """Async URL (asyncpg) for the SQLAlchemy async engine."""
        pw = self.postgres_password.get_secret_value()
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{pw}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """Sync URL (psycopg2) for Alembic CLI migrations."""
        pw = self.postgres_password.get_secret_value()
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{pw}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
