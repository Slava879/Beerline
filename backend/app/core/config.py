from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    ENV: str = 'dev'

    DATABASE_URL: str

    JWT_SECRET: str
    JWT_ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_LIFETIME_MINUTES: int = 15

    REFRESH_TOKEN_LIFETIME_DAYS: int = 30

settings = Settings()