"""FastAPI 앱 팩토리."""
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from korean_pii_gateway.config import Settings


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

    return app
