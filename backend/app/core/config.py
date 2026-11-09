from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file = BASE_DIR / ".env",
        env_file_encoding = "utf-8",
        extra = "ignore",  # this stops pydantic to raise an error for the keys in env that are not available in Settings
        case_sensitive = False
    )
    
    app_env: Literal["dev", "staging", "prod"] = "dev"
    app_name: str = "Indus Faultbook Assistant"
    cors_origins: str = "http://localhost:5173"


    db_host: str = "localhost"
    db_port: int | None = None
    db_driver: str = "{ODBC Driver 18 for SQL Server}"
    db_name: str = "SRS_flogbook"
    db_username: str = "sa"
    db_password: SecretStr = SecretStr("")
    db_trust_server_cert: bool = True
    db_timeout_seconds: int = 15
    
    llm_provider: Literal["ollama", "gemini"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout: int = 120000 #ms
    ollama_model: str = "lfm3:latest"
    ollama_think: bool = False
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_api_key: SecretStr = SecretStr("") # SecretStr prevents the password from appearing in logs, tracebacks and repr(settings)
    
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def db_server(self) -> str:
        if self.db_port is None:
            return self.db_host
        return f"{self.db_host},{self.db_port}"

    @property
    def db_connection_string(self) -> str:
        return (
            f"DRIVER={self.db_driver};"
            f"SERVER={self.db_server};"
            f"DATABASE={self.db_name};"
            f"UID={self.db_username};"
            f"PWD={self.db_password.get_secret_value()};"
            f"TrustServerCertificate={'yes' if self.db_trust_server_cert else 'no'};"
        )
    
    @model_validator(mode="after")
    def _validate_provider(self) -> "Settings":
        if self.llm_provider == "gemini" and not self.gemini_api_key.get_secret_value():
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        return self

settings = Settings()
