from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str           # z.B. postgresql://user:pw@db:5432/metering
    admin_username: str = "admin"
    admin_password: str = "changeme"   # via Env überschreiben!
    secret_key: str = "change-this-secret"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()