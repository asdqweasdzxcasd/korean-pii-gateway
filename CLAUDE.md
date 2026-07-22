# korean-pii-gateway

한국어 개인정보(PII) 탐지·마스킹 엔진(korean-pii, 의존성 0) + OpenAI 호환 FastAPI 프록시 + Open WebUI/Claude Code 어댑터. 상세 설계는 `docs/superpowers/` (spec·plan) 참조.

## 검증 (완료 판정 기준)

```bash
./scripts/verify   # ruff + pytest — exit 0 이어야 "완료"
```

- 모든 코드 변경은 verify 통과 후에만 완료로 보고한다
- 새 기능·버그 수정은 테스트 먼저 추가(TDD)
- venv 재구성: `uv venv && uv pip install -e packages/core -e packages/gateway pytest ruff`

## autodev 루프 (무인 개발 모드)

사용자가 개발 작업을 자연어로 요청하면:

1. **시작 시** `echo 0 > .claude/autodev.state` 를 실행해 루프를 활성화한다
2. 구현 → `./scripts/verify` → 실패 시 수정 반복 (Stop hook이 verify 실패 상태의 종료를 막아준다, 최대 8회)
3. **사람 결정이 필요한 blocker**(설계 선택, 외부 계정, 비용 발생)를 만나면
   `rm -f .claude/autodev.state` 후 상황을 보고하고 멈춘다
4. verify 통과로 종료되면 변경 요약과 커밋 여부를 보고한다

단순 질문·조사에는 루프를 켜지 않는다.

## 경계 (사람 승인 필요)

- `git push`, PyPI 발행(`uv publish`/`twine`), `docker push`, `gh release` — 자동 실행 금지 (settings.json의 ask 규칙과 동일)
- 시크릿·토큰을 코드/설정에 하드코딩하지 않는다

## 남은 릴리스 체크리스트 (MEMO.md 참조)

① PyPI 발행(korean-pii, korean-pii-gateway) ② 실 uvicorn SSE 수동 검증 ③ `/plugin install` 실세션 도그푸딩 ④ v0.1 태그
