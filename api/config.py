from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://autoest:autoest_secret@localhost:5432/autoest"
    secret_key: str = "change_me_in_prod"
    upload_dir: str = "/app/uploads"
    svg_dir: str = "/app/svgs"

    @model_validator(mode="after")
    def fix_db_url(self):
        # Railway provides postgres:// but SQLAlchemy requires postgresql://
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)
        return self

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
