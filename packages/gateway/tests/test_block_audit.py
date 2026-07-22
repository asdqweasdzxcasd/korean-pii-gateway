import json

from conftest import make_client

RRN_TEXT = "주민번호 990101-1234567"


def test_block_action_returns_openai_style_error(upstream_capture):
    with make_client(upstream_capture["app"], action="block") as client:
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "m", "messages": [{"role": "user", "content": RRN_TEXT}]},
        )
        assert resp.status_code == 400
        err = resp.json()["error"]
        assert err["code"] == "pii_detected"
        assert "rrn" in err["message"]
        assert "990101" not in json.dumps(resp.json())  # 원문 값 미노출
        assert "body" not in upstream_capture  # 업스트림에 전달되지 않음


def test_audit_log_written_without_raw_values(upstream_capture, tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    with make_client(upstream_capture["app"], audit_path=str(audit_file)) as client:
        client.post(
            "/v1/chat/completions",
            json={"model": "m", "messages": [{"role": "user", "content": RRN_TEXT}]},
        )
    line = json.loads(audit_file.read_text(encoding="utf-8").splitlines()[0])
    assert line["action"] == "mask"
    assert line["detections"] == {"rrn": 1}
    assert "990101" not in json.dumps(line)


def test_scan_failure_fail_closed(upstream_capture, monkeypatch):
    with make_client(upstream_capture["app"]) as client:  # fail_mode 기본 closed
        import korean_pii_gateway.app as app_mod

        def boom(body, mode):
            raise RuntimeError("엔진 오류")

        monkeypatch.setattr(app_mod, "scan_chat_body", boom)
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "m", "messages": [{"role": "user", "content": "안녕"}]},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "pii_scan_failed"


def test_scan_failure_fail_open_forwards(upstream_capture, monkeypatch):
    with make_client(upstream_capture["app"], fail_mode="open") as client:
        import korean_pii_gateway.app as app_mod

        def boom(body, mode):
            raise RuntimeError("엔진 오류")

        monkeypatch.setattr(app_mod, "scan_chat_body", boom)
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "m", "messages": [{"role": "user", "content": "안녕"}]},
        )
        assert resp.status_code == 200
        assert upstream_capture["body"]["messages"][0]["content"] == "안녕"


def test_bad_nested_body_returns_pii_scan_failed(upstream_capture):
    """dict이지만 messages가 리스트가 아닌 경우 — fail-closed try/except로 500 대신 400."""
    with make_client(upstream_capture["app"]) as client:
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "m", "messages": "not-a-list"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "pii_scan_failed"
