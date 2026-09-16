"""Application settings, loaded from environment variables / `.env`."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    api_keys: str = ""
    cache_ttl_seconds: int = 3600
    stock_quote_ttl_seconds: int = 300
    fundamentals_ttl_seconds: int = 86400
    crypto_quote_ttl_seconds: int = 300
    options_ttl_seconds: int = 86400
    bolsai_api_key: str = ""
    sec_edgar_contact_email: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def api_keys_set(self) -> set[str]:
        return {key.strip() for key in self.api_keys.split(",") if key.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
