"""업스트림 연결 실패 시 OpenAI 형식 502 응답을 반환하는지 검증."""
import httpx
from fastapi.testclient import TestClient

from korean_pii_gateway.app import create_app
from korean_pii_gateway.config import Settings


def _connect_error_handler(request):
    raise httpx.ConnectError("boom", request=request)


def test_upstream_connect_error_returns_502():
    settings = Settings(upstream_base_url="http://upstream")
    transport = httpx.MockTransport(_connect_error_handler)
    app = create_app(settings, transport=transport)
    with TestClient(app) as client:
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "m", "messages": [{"role": "user", "content": "안녕"}]},
        )
        assert resp.status_code == 502
        err = resp.json()["error"]
        assert err["code"] == "upstream_unreachable"
        assert "업스트림" in err["message"]
