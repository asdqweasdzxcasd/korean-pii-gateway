"""FastAPI 앱 팩토리."""
import json as _json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from korean_pii_gateway.audit import AuditLogger
from korean_pii_gateway.config import Settings
from korean_pii_gateway.scan import scan_chat_body

_FORWARD_HEADERS = {"authorization", "content-type", "openai-organization", "openai-project"}
_SKIP_RESPONSE_HEADERS = {"content-length", "transfer-encoding", "content-encoding", "connection"}


def _error(message: str, code: str) -> dict:
    return {
        "error": {
            "message": message,
            "type": "invalid_request_error",
            "code": code,
            "param": None,
        }
    }


def create_app(
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    audit = AuditLogger(settings.audit_path)

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
                content=_error("요청 본문이 유효한 JSON 객체가 아닙니다.", "invalid_body"),
            )
        try:
            scanned, detections = scan_chat_body(body, settings.mask_mode)
        except Exception:
            audit.log("scan_failed", [])
            if settings.fail_mode == "closed":
                return JSONResponse(
                    status_code=400,
                    content=_error(
                        "PII 검사에 실패해 요청을 차단했습니다 (fail-closed).",
                        "pii_scan_failed",
                    ),
                )
            scanned, detections = body, []
        if detections and settings.action == "block":
            types = sorted({d.type for d in detections})
            audit.log("block", detections)
            return JSONResponse(
                status_code=400,
                content=_error(
                    f"개인정보가 탐지되어 차단했습니다: {', '.join(types)}",
                    "pii_detected",
                ),
            )
        audit.log("mask" if detections else "pass", detections)
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
