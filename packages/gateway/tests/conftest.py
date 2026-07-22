"""테스트 공용 픽스처 — 가짜 업스트림(받은 요청을 그대로 노출)."""
import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from korean_pii_gateway.app import create_app
from korean_pii_gateway.config import Settings


@pytest.fixture
def upstream_capture():
    captured = {}
    upstream = FastAPI()

    @upstream.post("/v1/chat/completions")
    async def chat(request: Request):
        captured["body"] = await request.json()
        captured["auth"] = request.headers.get("authorization")
        return JSONResponse({"id": "chatcmpl-test", "choices": []})

    captured["app"] = upstream
    return captured


def make_client(upstream_app, **settings_kw):
    settings = Settings(upstream_base_url="http://upstream", **settings_kw)
    transport = httpx.ASGITransport(app=upstream_app)
    app = create_app(settings, transport=transport)
    return TestClient(app)
