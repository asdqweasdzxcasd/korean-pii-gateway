# korean-pii-gateway

LLM API로 나가는 요청에서 한국어 개인정보(주민등록번호·전화번호·계좌번호 등)를 탐지해 마스킹·차단하는 셀프호스팅 게이트웨이입니다.

## 중요 고지

이 프로젝트는 **보조 방어 계층**이며, 어떤 법적·규제적 컴플라이언스(개인정보보호법, GDPR 등)도 보장하지 않습니다. 정규식 기반 탐지 방식의 한계로 탐지 누락(미탐지)이 발생할 수 있으며, 민감한 데이터를 다루는 환경에서는 반드시 별도의 검토·승인 절차와 함께 사용해야 합니다. 이 게이트웨이를 통과했다고 해서 요청에 개인정보가 없다고 보장할 수 없습니다.

## 빠른 시작

세 가지 방법으로 실행할 수 있습니다.

### 1) pip 설치

```bash
pip install korean-pii-gateway
export KPG_UPSTREAM_BASE_URL=https://api.openai.com
uvicorn --factory korean_pii_gateway.app:create_app --host 0.0.0.0 --port 8500
```

### 2) Docker

```bash
docker build -t korean-pii-gateway .
docker run -d --rm -p 8500:8500 \
  -e KPG_UPSTREAM_BASE_URL=https://api.openai.com \
  --name kpg korean-pii-gateway
```

### 3) docker-compose

`docker-compose.example.yml`을 `docker-compose.yml`로 복사한 뒤 필요한 값을 수정하고 실행합니다.

```bash
cp docker-compose.example.yml docker-compose.yml
docker compose up -d
```

### 클라이언트 연결

기존 OpenAI SDK 코드에서 `base_url`만 게이트웨이 주소로 바꾸면 됩니다. 요청은 그대로 `KPG_UPSTREAM_BASE_URL`로 지정한 업스트림(OpenAI, 또는 Anthropic의 OpenAI 호환 엔드포인트 등)으로 전달되며, 그 전에 메시지 내용이 검사·마스킹(또는 차단)됩니다.

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8500/v1",
    api_key="실제-업스트림-API-키",  # 게이트웨이는 그대로 전달만 하며 저장하지 않음
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "제 전화번호는 010-1234-5678입니다. 연락 주세요."}
    ],
)
print(response.choices[0].message.content)
```

`KPG_ACTION=mask`(기본값)인 경우 위 요청은 업스트림으로 전달되기 전에 `•••-••••-5678`처럼 마스킹됩니다(끝 4자리만 보존). `KPG_ACTION=block`이면 개인정보가 탐지된 요청 자체를 OpenAI 표준 에러 형식(HTTP 400)으로 거부합니다.

## 엔진 단독 사용

게이트웨이 없이 탐지·마스킹 엔진(`korean-pii`)만 라이브러리로 쓸 수도 있습니다. 외부 의존성이 없는 순수 파이썬 패키지입니다.

```bash
pip install korean-pii
```

```python
from korean_pii import detect, mask, MaskPolicy

text = "주민번호 900101-1234567, 문의는 010-1234-5678로 부탁드립니다."

# 탐지만 수행 — 타입과 위치(span)를 반환
for d in detect(text):
    print(d.type, d.start, d.end)

# 마스킹까지 수행
result = mask(text, MaskPolicy(mode="format"))
print(result.text)
# -> "주민번호 900101-1••••••, 문의는 •••-••••-5678로 부탁드립니다."
```

## 탐지 타입

V1은 전부 정규식 + 유효성 검증 방식이며 NER은 사용하지 않습니다.

| 타입 | 오탐 억제 방식 |
|------|-----------|
| 주민등록번호 | 생년월일 유효성 + 체크섬 |
| 외국인등록번호 | 동일 체크섬 체계 |
| 휴대폰·전화번호 | 010/지역번호 프리픽스 + 자릿수 |
| 신용카드번호 | Luhn 체크섬 |
| 계좌번호 | 은행명 키워드 근접 문맥 조건부 (단독 숫자열 오탐 방지) |
| 이메일 | 형식 검증 |
| 여권번호·운전면허번호 | 형식 검증 |
| API 키/시크릿 | 고유 프리픽스 (sk-, AKIA 등 주요 패턴) |

마스킹은 원래 형식을 최대한 보존하는 형식 보존 마스킹이 기본값(`900101-1••••••`)이며, 설정으로 플레이스홀더(`[주민등록번호]`) 방식도 선택할 수 있습니다.

## 환경변수

| 변수 | 기본값 | 허용값 | 설명 |
|------|--------|--------|------|
| `KPG_UPSTREAM_BASE_URL` | `https://api.openai.com` | URL | 실제 요청을 전달할 업스트림 API 주소 |
| `KPG_ACTION` | `mask` | `mask`, `block` | 개인정보 탐지 시 마스킹 후 전달할지, 요청 자체를 차단할지 |
| `KPG_FAIL_MODE` | `closed` | `closed`, `open` | 탐지 로직 자체가 실패했을 때 요청을 막을지(`closed`), 그대로 통과시킬지(`open`) |
| `KPG_MASK_MODE` | `format` | `format`, `placeholder` | 마스킹 방식 — 형식 보존(`format`) 또는 타입 이름 플레이스홀더(`placeholder`) |
| `KPG_AUDIT_LOG` | (미설정 = stdout) | 파일 경로 | 감사 로그(JSONL)를 남길 파일 경로. 미설정 시 표준 출력으로 기록되어 `docker logs`로 수집 가능 |

감사 로그에는 탐지된 개인정보의 **원문 값은 절대 기록되지 않으며**, 타입별 개수와 액션만 남습니다. 예:

```json
{"ts": "2026-07-22T09:12:34+00:00", "action": "mask", "detections": {"phone": 1, "rrn": 1}}
```

## 벤치마크

탐지 품질은 이 프로젝트의 핵심 자산 중 하나입니다. 오탐(false positive) 억제 여부를 검증하기 위해 개인정보가 없는 일반 한국어 뉴스·코드 텍스트로 구성된 오탐 코퍼스 테스트를 두고 있으며, 이 코퍼스에서 탐지 결과가 0건이어야 통과합니다.

재현:

```bash
pytest packages/core/tests/test_corpus.py
```

코퍼스 확장과 함께 유효 PII 재현율(recall) 수치 표는 추후 채워질 예정입니다.

## 어댑터

게이트웨이 없이 클라이언트 쪽에서 바로 붙일 수 있는 어댑터 2종을 제공합니다. 둘 다 위의 "보조 방어 계층" 고지가 그대로 적용됩니다 — 정규식 기반 탐지의 한계로 미탐지가 발생할 수 있으므로 유일한 방어선으로 의존하지 마세요.

### Open WebUI

Open WebUI의 Function(Filter) 기능으로 등록해 대화 메시지가 모델로 전송되기 전에 마스킹합니다.

1. `adapters/openwebui/korean_pii_filter.py`의 내용을 복사합니다.
2. Open WebUI 관리자 화면(`설정 → 관리자 설정 → Functions`)에서 "함수 추가"를 누르고 코드를 붙여넣어 저장합니다. 또는 openwebui.com 커뮤니티 함수 등록 절차를 따라 동일한 코드를 배포해도 됩니다.
3. 워크스페이스 또는 모델 설정에서 이 Filter를 활성화합니다(`Valves`의 `mask_mode`로 `format`/`placeholder` 방식을 선택할 수 있습니다).
4. 실행 환경에 `korean-pii` 패키지가 설치되어 있어야 합니다(`pip install korean-pii`). Open WebUI 컨테이너에 직접 설치하거나, 커스텀 이미지를 빌드할 때 포함하세요.

### Claude Code 플러그인

`UserPromptSubmit` 훅으로 등록되어, 사용자가 입력한 프롬프트에 한국어 개인정보가 감지되면 Claude로 전송되기 전에 차단하고 마스킹된 버전을 제안합니다.

사전 조건: 훅을 실행할 환경(로컬 머신)에 `korean-pii` 패키지가 설치되어 있어야 합니다.

```bash
pip install korean-pii
```

설치:

```
/plugin marketplace add asdqweasdzxcasd/korean-pii-gateway
/plugin install korean-pii-guard@korean-pii-gateway
```

설치 후 개인정보가 포함된 프롬프트(예: 주민등록번호, 전화번호)를 입력하면 전송이 차단되고, 마스킹된 버전으로 다시 시도하라는 안내 메시지가 표시됩니다. 훅 로직 자체(마스킹 결과·차단 조건)는 `pytest packages/core/tests/test_claude_code_adapter.py`로 검증되어 있으며, `claude plugin validate`로 플러그인·마켓플레이스 매니페스트 형식도 확인되어 있습니다. 다만 `/plugin marketplace add` → `/plugin install` → 실제 세션에서의 차단 동작 확인은 로컬 `claude` 세션에서 사용자가 직접 한 번 실행해 보는 것을 권장합니다.

## 라이선스

MIT
