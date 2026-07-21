# korean-pii-gateway 설계 (2026-07-21 확정)

## 개요

한국어 개인정보(PII)를 LLM API로 보내기 전에 탐지·마스킹·차단하는 설치형 오픈소스.
호스팅 서비스가 아니라 **사용자 로컬/사내에서 실행**하는 구조 — "개인정보가 외부로 나가지 않는다"가 제품의 전제이므로 웹 서비스 형태는 채택하지 않는다.

- 배포 형태: **설치형 OSS, public 레포** (PyPI + Docker Hub + GitHub)
- 포지셔닝: 컴플라이언스 보장이 아닌 **보조 방어 계층** (탐지 누락 가능성 명시)
- 목적: 실사용 가치 + AI 백엔드 이직 포트폴리오 (탐지 품질 벤치마크가 핵심 자산)

## 결정 사항 요약

| 항목 | 결정 | 근거 |
|------|------|------|
| 배포 형태 | 설치형 OSS만 (public) | 호스팅형은 "우리 서버에 PII를 보내는" 자기모순. 경쟁 제품 전부 셀프호스팅 |
| V1 범위 | PII 차단 코어만 | 장애 시뮬레이터·정책 엔진·NER은 이후. mvp-scope 원칙 |
| 프로토콜 | OpenAI 형식(`/v1/chat/completions`)만 | 사실상 표준. Claude도 Anthropic의 OpenAI 호환 엔드포인트로 지원됨. Anthropic 네이티브(`/v1/messages`)는 이후 (Claude Code 트래픽 직접 프록시용) |
| 구조 | 엔진 중심 + 멀티 어댑터 | 유통 채널 조사 결과(아래) 반영 |
| 이름 | korean-pii-gateway / korean-pii | 브랜드성보다 기능이 드러나는 이름 선택 |

## 유통 채널 조사 결과 (2026-07-21)

- **OpenAI GPT Store**: 부적합. ChatGPT 안에서 실행되는 구조라 데이터가 이미 OpenAI에 도착한 뒤 — "보내기 전 차단" 제품은 원리적으로 올릴 수 없음.
- **PyPI / Docker Hub**: 기본 채널.
- **Open WebUI Filter Function**: 유력. 커뮤니티 함수 마켓에 "Nordic PII Filter" 선례 존재, 한국어판 부재. 파이썬 파일 1개로 등록 가능.
- **Claude Code 플러그인 마켓플레이스**: 유력. 마켓플레이스 = git 레포(marketplace.json), 심사 없음. `UserPromptSubmit` 훅으로 전송 전 검사 가능. 본인 도그푸딩 가능.
- **Chrome 확장**: 레드오션 (로컬 WASM 처리 제품 다수 존재). 후순위.
- 기존 영어권 유사 오픈소스: aisecuritygateway, LLM-Redactor, ceil-dlp, LLMProxy, PasteGuard 등. **한국어 특화(주민번호 체크섬, 한국식 형식)는 공백** — 이것이 차별점.

## 저장소 구조 (public 모노레포)

```
korean-pii-gateway/
  packages/
    core/            # 탐지 엔진 korean-pii — 순수 Python, 의존성 0
    gateway/         # FastAPI 프록시 korean-pii-gateway — core에 의존
  adapters/
    openwebui/       # Filter Function 파일 1개
    claude-code/     # 플러그인 (marketplace.json + UserPromptSubmit 훅)
  docs/              # 한글 튜토리얼 ("사내 문서를 LLM에 보내기 전 개인정보 제거")
  Dockerfile
  docker-compose.example.yml
```

- PyPI 발행: `korean-pii`(엔진), `korean-pii-gateway`(게이트웨이) 별도 패키지.
  엔진만 임베드하는 개발자(FastAPI/LangChain 예제 대상)와 게이트웨이 사용자를 모두 커버.
- 어댑터는 별도 패키지가 아닌 엔진을 감싸는 얇은 파일. 이 레포 자체가 Claude Code 마켓플레이스 역할.

## 탐지 엔진 (packages/core) — 본체

공개 API 두 개:

```python
detect(text) -> list[Detection]              # 타입, 위치(span), 검증 근거
mask(text, policy) -> (masked_text, list[Detection])
```

V1 탐지 대상 (전부 정규식 + 유효성 검증, NER 없음):

| 타입 | 오탐 억제 |
|------|-----------|
| 주민등록번호 | 생년월일 유효성 + 체크섬 |
| 외국인등록번호 | 동일 체크섬 체계 |
| 휴대폰·전화번호 | 010/지역번호 프리픽스 + 자릿수 |
| 신용카드번호 | Luhn 체크섬 |
| 계좌번호 | 은행명 키워드 근접 문맥 조건부 (단독 숫자열 오탐 방지) |
| 이메일 | 형식 검증 |
| 여권번호·운전면허번호 | 형식 검증 |
| API 키/시크릿 | 고유 프리픽스 (sk-, AKIA 등 주요 패턴) |

- 마스킹: **형식 보존 마스킹 기본** (`900101-1••••••`), 플레이스홀더(`[주민등록번호]`) 선택 가능.
- 품질 목표 = 포트폴리오 자산: 일반 한국어 코퍼스(뉴스·코드) 오탐 0건, 유효 PII 재현율 표를 README에 벤치마크로 공개.

## 게이트웨이 (packages/gateway)

- 엔드포인트: `POST /v1/chat/completions` (스트리밍 포함), `GET /health`. V1은 이 둘만.
- 검사 대상: 요청 `messages[].content` (문자열 + 멀티모달 text 파트). **응답 방향 검사는 V1 제외.**
- 액션: `mask`(기본, 마스킹 후 전달) / `block`(OpenAI 표준 에러 형식 400, 걸린 타입 명시).
- **BYOK**: 클라이언트 `Authorization` 헤더를 업스트림에 패스스루. 게이트웨이는 API 키를 저장하지 않음. 업스트림 base URL은 설정값.
- 설정: 환경변수 + 선택적 YAML (타입별 on/off, 액션, 업스트림 URL).
- 감사 로그: JSONL — 탐지 타입·개수·액션만 기록. **원문 PII 값은 절대 기록하지 않음.**
- 장애 처리: 엔진 검사 실패 시 **fail-closed(차단) 기본**, 설정으로 fail-open 가능. 업스트림 오류·타임아웃은 그대로 패스스루.

## 어댑터 (엔진 완성 후 각 1일 작업)

- **Open WebUI Filter Function**: `inlet()`에서 `mask()` 호출하는 단일 파일. openwebui.com 커뮤니티 등록. "Nordic PII Filter"의 한국어판 포지션.
- **Claude Code 플러그인**: 레포 루트에 `marketplace.json`, `UserPromptSubmit` 훅이 프롬프트를 엔진으로 검사(마스킹/경고/차단). 설치: `/plugin marketplace add <레포>`.

## 테스트 전략 (TDD)

- 엔진: 케이스 테이블 기반 단위 테스트
  - 유효 세트: 체크섬 통과 주민번호 등 → 탐지 확인
  - 무효 세트: 형식은 맞지만 체크섬 실패 → 미탐지 확인
  - 오탐 코퍼스: 일반 한국어 뉴스·코드 텍스트 → 탐지 0건 확인
- 게이트웨이: mock 업스트림으로 마스킹/차단/스트리밍 패스스루 통합 테스트. 스트리밍 무결성이 핵심 검증점.
- 어댑터: 엔진 결과 반영 스모크 테스트.

## V1 이후 후보 (순서 미정)

- Anthropic 네이티브 프로토콜(`/v1/messages`) — Claude Code/SDK 트래픽 직접 프록시
- LLM 장애 시뮬레이터 흡수 (429·지연·잘린 SSE·깨진 tool-call JSON 주입)
- 정책 엔진 확장 (allow/deny 규칙), NER 기반 이름·주소 탐지
- Chrome 확장 (JS/WASM 포팅 필요, 별도 제품)

## 리스크

- 탐지 누락 → "보조 방어 계층" 포지셔닝을 README 첫 화면에 명시
- 계좌번호 등 문맥 의존 타입의 오탐/미탐 트레이드오프 → 문맥 조건부 + 벤치마크로 투명 공개
- PyPI 패키지명 선점 여부 → 레포/패키지 생성 시 확인
