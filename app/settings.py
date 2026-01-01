from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    METALS_DEV_API_KEY: str | None = None
    BASE_CURRENCY: str = "USD"

    # Zoho Books
    ZOHO_CLIENT_ID: str | None = None
    ZOHO_CLIENT_SECRET: str | None = None
    ZOHO_REFRESH_TOKEN: str | None = None
    ZOHO_ORG_ID: str | None = None
    ZOHO_DC: str = "us"  # us, eu, in, au, ca
    ZOHO_AUTO_SYNC_JOBS: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
