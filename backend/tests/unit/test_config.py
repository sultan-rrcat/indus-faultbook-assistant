import pytest
from pydantic import SecretStr

from app.core.config import Settings


def test_connection_string_uses_real_password() -> None:
    settings = Settings(
        db_host="db01",
        db_port=1433,
        db_password=SecretStr("s3cret"),
        db_trust_server_cert=False,
    )

    connection_string = settings.db_connection_string

    assert "SERVER=db01,1433" in connection_string
    assert "PWD=s3cret" in connection_string
    assert "**********" not in connection_string
    assert "TrustServerCertificate=no" in connection_string


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = Settings(cors_origins="http://a, http://b")
    assert settings.cors_origin_list == ["http://a", "http://b"]


def test_gemini_provider_requires_api_key() -> None:
    with pytest.raises(ValueError):
        Settings(llm_provider="gemini", gemini_api_key=SecretStr(""))
