from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://autoest:autoest_secret@localhost:5432/autoest"
    secret_key: str = "change_me_in_prod"
    upload_dir: str = "/app/uploads"
    svg_dir: str = "/app/svgs"

    def __init__(self, **data):
        super().__init__(**data)
        # Railway provides postgres:// but SQLAlchemy requires postgresql://
        if self.database_url.startswith("postgres://"):
            object.__setattr__(self, "database_url", self.database_url.replace("postgres://", "postgresql://", 1))

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
