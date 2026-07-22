from conftest import make_client

RRN_TEXT = "내 주민번호는 990101-1234567 이야"


def test_masks_pii_before_forwarding(upstream_capture):
    with make_client(upstream_capture["app"]) as client:
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": RRN_TEXT}]},
            headers={"Authorization": "Bearer sk-user-key-abcdefghij123456"},
        )
        assert resp.status_code == 200
        sent = upstream_capture["body"]["messages"][0]["content"]
        assert "990101-1••••••" in sent
        assert "1234567" not in sent


def test_authorization_header_passthrough(upstream_capture):
    with make_client(upstream_capture["app"]) as client:
        client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "안녕"}]},
            headers={"Authorization": "Bearer test-token"},
        )
        assert upstream_capture["auth"] == "Bearer test-token"


def test_masks_multimodal_text_parts(upstream_capture):
    with make_client(upstream_capture["app"]) as client:
        client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": RRN_TEXT},
                        {"type": "image_url", "image_url": {"url": "http://x/img.png"}},
                    ],
                }],
            },
        )
        parts = upstream_capture["body"]["messages"][0]["content"]
        assert "1234567" not in parts[0]["text"]
        assert parts[1]["image_url"]["url"] == "http://x/img.png"  # 비텍스트 파트는 그대로


def test_invalid_json_body_returns_400(upstream_capture):
    with make_client(upstream_capture["app"]) as client:
        resp = client.post(
            "/v1/chat/completions",
            content=b"{not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_body"


def test_non_object_json_body_returns_400(upstream_capture):
    with make_client(upstream_capture["app"]) as client:
        resp = client.post(
            "/v1/chat/completions",
            json=[1, 2, 3],
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "invalid_body"


def test_disallowed_headers_are_not_forwarded(upstream_capture):
    with make_client(upstream_capture["app"]) as client:
        client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "안녕"}]},
            headers={"Cookie": "secret=1"},
        )
        assert "cookie" not in upstream_capture["headers"]
