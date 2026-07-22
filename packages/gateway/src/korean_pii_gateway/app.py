"""FastAPI 앱 팩토리."""
import json as _json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from korean_pii_gateway.config import Settings
from korean_pii_gateway.scan import scan_chat_body

_FORWARD_HEADERS = {"authorization", "content-type", "openai-organization", "openai-project"}
_SKIP_RESPONSE_HEADERS = {"content-length", "transfer-encoding", "content-encoding", "connection"}


def create_app(
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.client = httpx.AsyncClient(transport=transport, timeout=120.0)
        yield
        await app.state.client.aclose()

    app = FastAPI(title="korean-pii-gateway", lifespan=lifespan)
    app.state.settings = settings

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = None
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": "요청 본문이 유효한 JSON 객체가 아닙니다.",
                        "type": "invalid_request_error",
                        "code": "invalid_body",
                        "param": None,
                    }
                },
            )
        scanned, detections = scan_chat_body(body, settings.mask_mode)
        headers = {
            k: v for k, v in request.headers.items() if k.lower() in _FORWARD_HEADERS
        }
        upstream_req = app.state.client.build_request(
            "POST",
            settings.upstream_base_url + "/v1/chat/completions",
            content=_json.dumps(scanned, ensure_ascii=False).encode(),
            headers={**headers, "content-type": "application/json"},
        )
        upstream_resp = await app.state.client.send(upstream_req, stream=True)
        resp_headers = {
            k: v
            for k, v in upstream_resp.headers.items()
            if k.lower() not in _SKIP_RESPONSE_HEADERS
        }
        return StreamingResponse(
            upstream_resp.aiter_raw(),
            status_code=upstream_resp.status_code,
            headers=resp_headers,
            background=BackgroundTask(upstream_resp.aclose),
        )

    return app
