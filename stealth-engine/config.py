from pydantic_settings import BaseSettings


class StealthSettings(BaseSettings):
    CHROMIUM_POOL_SIZE: int = 4
    FIREFOX_POOL_SIZE: int = 2
    HEADLESS: bool = True
    BLOCK_ADS: bool = True
    PORT: int = 8888

    model_config = {"env_prefix": "STEALTH_"}


class SentrySettings(BaseSettings):
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "production"


settings = StealthSettings()
sentry_settings = SentrySettings()
