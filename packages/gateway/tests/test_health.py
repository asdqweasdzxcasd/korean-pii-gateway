from fastapi.testclient import TestClient

from korean_pii_gateway.app import create_app
from korean_pii_gateway.config import Settings


def test_health_returns_ok():
    app = create_app(Settings(upstream_base_url="http://upstream"))
    client = TestClient(app)
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
