#!/usr/bin/env bash
# autodev 조건부 Stop Hook — "작업 하나를 무인으로 완료하는 자동 루프"
#
# 동작:
#  - .claude/autodev.state 가 없으면: 일반 세션 → 아무것도 안 함 (즉시 종료 허용)
#  - 있으면: scripts/verify 실행
#      · 성공  → 플래그 제거, 종료 허용 (완료 보고)
#      · 실패  → 반복 횟수 +1 후 decision:block 으로 세션을 계속시켜 수정 유도
#      · 반복 상한(MAX_ITER) 도달 → 플래그 제거, 종료 허용 (미해결 보고)
#
# 시작/종료 규약 (CLAUDE.md 참고):
#  - Claude가 autodev 작업을 시작할 때: echo 0 > .claude/autodev.state
#  - 사람 결정이 필요한 blocker를 만나면: 플래그를 스스로 제거하고 보고 후 종료
set -u
cd "$(dirname "$0")/.."

STATE=.claude/autodev.state
MAX_ITER=8

# 일반 세션: 개입하지 않음
[ -f "$STATE" ] || exit 0

ITER=$(cat "$STATE" 2>/dev/null || echo 0)
case "$ITER" in (*[!0-9]*|"") ITER=0;; esac

if [ "$ITER" -ge "$MAX_ITER" ]; then
  rm -f "$STATE"
  printf '{"systemMessage":"[autodev] 반복 상한(%d회) 도달 — 루프 종료. 남은 문제를 수동 확인하세요."}\n' "$MAX_ITER"
  exit 0
fi

OUT=$(./scripts/verify 2>&1)
if [ $? -eq 0 ]; then
  rm -f "$STATE"
  printf '{"systemMessage":"[autodev] verify 통과 — 작업 완료로 종료합니다. (반복 %s회)"}\n' "$ITER"
  exit 0
fi

echo $((ITER + 1)) > "$STATE"
# verify 실패 → 세션 계속 (마지막 30줄을 이유로 전달)
TAIL=$(printf '%s' "$OUT" | tail -30)
python3 - "$ITER" <<'PY' "$TAIL"
import json, sys
iter_n = sys.argv[1]
tail = sys.argv[2] if len(sys.argv) > 2 else ""
print(json.dumps({
    "decision": "block",
    "reason": (
        f"[autodev 루프 {int(iter_n)+1}/8] scripts/verify 실패. 아래 출력을 보고 문제를 수정한 뒤 "
        "다시 ./scripts/verify 를 실행해 통과시켜라. 사람 결정이 필요한 blocker면 "
        ".claude/autodev.state 를 삭제하고 상황을 보고하라.\n\n=== verify 출력(끝 30줄) ===\n" + tail
    ),
}, ensure_ascii=False))
PY
exit 0
