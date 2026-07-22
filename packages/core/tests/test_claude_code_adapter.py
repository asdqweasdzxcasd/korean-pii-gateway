import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).parents[3] / "adapters" / "claude-code" / "hooks" / "check_prompt.py"


def _run_hook(prompt: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"prompt": prompt}),
        capture_output=True, text=True, timeout=10,
    )


def test_clean_prompt_passes():
    result = _run_hook("이 함수 리팩터링해줘")
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_pii_prompt_blocked_with_masked_suggestion():
    result = _run_hook("주민번호 990101-1234567 처리해줘")
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["decision"] == "block"
    assert "rrn" in out["reason"] or "주민등록번호" in out["reason"]
    assert "1234567" not in out["reason"]          # 원문 미노출
    assert "990101-1••••••" in out["reason"]      # 마스킹된 제안문 포함
