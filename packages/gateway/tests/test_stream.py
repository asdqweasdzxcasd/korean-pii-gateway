"""SSE 스트리밍 패스스루 회귀 테스트."""
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from conftest import make_client

SSE_CHUNKS = [
    b'data: {"choices":[{"delta":{"content":"\xec\x95\x88"}}]}\n\n',
    b'data: {"choices":[{"delta":{"content":"\xeb\x85\x95"}}]}\n\n',
    b"data: [DONE]\n\n",
]


@pytest.fixture
def sse_upstream():
    upstream = FastAPI()

    @upstream.post("/v1/chat/completions")
    async def chat():
        async def gen():
            for chunk in SSE_CHUNKS:
                yield chunk

        return StreamingResponse(gen(), media_type="text/event-stream")

    return upstream


def test_sse_bytes_pass_through_unmodified(sse_upstream):
    with make_client(sse_upstream) as client:
        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={"model": "m", "stream": True,
                  "messages": [{"role": "user", "content": "안녕"}]},
        ) as resp:
            received = b"".join(resp.iter_bytes())
        assert received == b"".join(SSE_CHUNKS)
        assert resp.headers["content-type"].startswith("text/event-stream")
