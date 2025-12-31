from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    METALS_DEV_API_KEY: str | None = None
    BASE_CURRENCY: str = "USD"

    class Config:
        env_file = ".env"

settings = Settings()
