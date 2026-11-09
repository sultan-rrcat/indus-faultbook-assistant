import pytest

from app.core.config import settings
from app.services.providers.gemini import _build_http_options


def test_build_http_options_none_without_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "https_proxy", "")
    monkeypatch.setattr(settings, "http_proxy", "")

    assert _build_http_options() is None


def test_build_http_options_prefers_https_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "https_proxy", "http://user:pass@proxy.local:3128")
    monkeypatch.setattr(settings, "http_proxy", "http://other.local:3128")

    options = _build_http_options()

    assert options is not None
    assert options.client_args == {"proxy": "http://user:pass@proxy.local:3128"}


def test_build_http_options_falls_back_to_http_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "https_proxy", "")
    monkeypatch.setattr(settings, "http_proxy", "http://proxy.local:3128")

    options = _build_http_options()

    assert options is not None
    assert options.client_args == {"proxy": "http://proxy.local:3128"}
