from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_URL: str
    ADMIN_TELEGRAM_ID: int = 6350942589
    GOOGLE_API_KEY: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    POSTGRES_CONNECTION_STRING: str

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()
