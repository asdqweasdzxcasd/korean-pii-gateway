import pytest
from fastapi.testclient import TestClient

from korean_pii_gateway.app import create_app
from korean_pii_gateway.config import Settings


def test_health_returns_ok():
    app = create_app(Settings(upstream_base_url="http://upstream"))
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("KPG_UPSTREAM_BASE_URL", "http://example:8000/")
    monkeypatch.setenv("KPG_ACTION", "block")
    s = Settings.from_env()
    assert s.upstream_base_url == "http://example:8000"  # 끝 슬래시 제거
    assert s.action == "block"
    assert s.fail_mode == "closed"  # 기본값


def test_settings_rejects_invalid_fail_mode():
    # fail_mode 오타("close")가 조용히 무시되어 fail-open처럼 동작하면 안 됨 — 기동 시점에 fail-fast
    with pytest.raises(ValueError):
        Settings(upstream_base_url="http://u", fail_mode="close")
