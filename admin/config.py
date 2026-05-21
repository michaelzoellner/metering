from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote_plus

class Settings(BaseSettings):
    postgres_user:     str
    postgres_password: str
    postgres_host:     str = "db"
    postgres_port:     int = 5432
    postgres_db:       str

    admin_username: str = "admin"
    admin_password: str = "changeme"
    secret_key:     str = "change-this-secret"

    @computed_field
    @property
    def database_url(self) -> str:
        pw = quote_plus(self.postgres_password)  # enkodiert ^ und alle anderen Sonderzeichen
        return f"postgresql://{self.postgres_user}:{pw}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()