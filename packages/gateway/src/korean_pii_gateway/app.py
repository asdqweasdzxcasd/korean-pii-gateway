"""FastAPI 앱 팩토리."""
import httpx
from fastapi import FastAPI

from korean_pii_gateway.config import Settings


def create_app(
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="korean-pii-gateway")
    app.state.settings = settings
    app.state.client = httpx.AsyncClient(transport=transport, timeout=120.0)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.on_event("shutdown")
    async def shutdown():
        await app.state.client.aclose()

    return app
