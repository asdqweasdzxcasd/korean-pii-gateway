#!/usr/bin/env python3
"""UserPromptSubmit 훅: 프롬프트에서 한국어 PII를 탐지하면 차단하고 마스킹본을 제안한다."""
import json
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        prompt = payload.get("prompt", "")
        from korean_pii import mask

        result = mask(prompt)
        if not result.detections:
            return 0
        types = ", ".join(sorted({d.type for d in result.detections}))
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"개인정보({types})가 감지되어 전송을 차단했습니다.\n"
                f"마스킹된 버전으로 다시 보내세요:\n{result.text}"
            ),
        }, ensure_ascii=False))
        return 0
    except Exception as e:  # korean-pii 미설치 등 — 훅 오류로 세션을 막지 않는다
        print(f"korean-pii-guard 훅 오류: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
