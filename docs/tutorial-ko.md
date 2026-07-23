# 사내 문서를 LLM에 보내기 전 개인정보 제거하기

사내 문서, 고객 상담 기록, CS 로그를 ChatGPT나 Claude에 요약·분석시키고 싶은데 주민등록번호·전화번호·계좌번호가 섞여 있어 망설여진다면 — 이 가이드가 그 문제를 다룹니다. `korean-pii`는 한국어 개인정보를 탐지·마스킹하는 오픈소스 엔진이고, 상황에 따라 네 가지 방식으로 쓸 수 있습니다.

> **먼저 알아둘 것**: 이 도구는 보조 방어 계층입니다. 정규식 + 체크섬 검증 기반이라 오탐은 적지만, 모든 개인정보(특히 이름·주소 같은 비정형 정보)를 잡아내지는 못합니다. 법적 컴플라이언스를 보장하지 않으며, 조직의 정책·법무 검토를 대체할 수 없습니다.

## 방식 1 — 파이썬 라이브러리로 직접 마스킹 (개인·스크립트)

가장 단순한 방식입니다. LLM 호출 전에 텍스트를 한 번 통과시킵니다.

```bash
pip install korean-pii
```

```python
from korean_pii import detect, mask, MaskPolicy

text = open("상담기록.txt", encoding="utf-8").read()

result = mask(text)                      # 형식 보존 마스킹 (기본)
print(result.text)                       # 990101-1234567 → 990101-1••••••

for d in result.detections:              # 무엇이 잡혔는지 확인 (원문 값은 로그에 남기지 말 것)
    print(d.type, d.start, d.end)

# 플레이스홀더 방식을 원하면:
result = mask(text, MaskPolicy(mode="placeholder"))   # → [주민등록번호]
```

폴더 전체를 일괄 처리하는 스크립트:

```python
from pathlib import Path
from korean_pii import mask

for f in Path("docs_in").glob("*.txt"):
    masked = mask(f.read_text(encoding="utf-8")).text
    (Path("docs_out") / f.name).write_text(masked, encoding="utf-8")
```

RAG 파이프라인이라면 **임베딩 생성 전**(벡터 DB 투입 전)에 마스킹하는 것이 중요합니다. 벡터 DB에 들어간 개인정보는 검색 결과로 계속 재유출되기 때문입니다.

## 방식 2 — 게이트웨이 프록시 (팀·사내 공용)

코드를 한 줄도 못 고치는 기존 도구가 많거나, 팀 전체에 일괄 적용하고 싶다면 프록시를 세웁니다. 클라이언트는 base URL만 바꾸면 됩니다.

```bash
pip install korean-pii-gateway
uvicorn --factory korean_pii_gateway.app:create_app --port 8500
```

또는 Docker:

```bash
git clone https://github.com/asdqweasdzxcasd/korean-pii-gateway
cd korean-pii-gateway && docker compose -f docker-compose.example.yml up -d
```

클라이언트 쪽 (OpenAI SDK):

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8500/v1",   # 이 줄만 추가
    api_key="sk-...",                      # 키는 게이트웨이가 저장하지 않고 그대로 전달(BYOK)
)
resp = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "이 상담기록 요약해줘: ..."}],
)
```

LangChain도 동일합니다:

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o", base_url="http://localhost:8500/v1", api_key="sk-...")
```

### Claude로 쓰기

게이트웨이의 입구는 OpenAI 호환 형식이지만, 뒷단은 자유입니다. Anthropic이 공식 제공하는 OpenAI 호환 엔드포인트를 업스트림으로 지정하면 Claude가 응답합니다:

```bash
KPG_UPSTREAM_BASE_URL=https://api.anthropic.com \
  uvicorn --factory korean_pii_gateway.app:create_app --port 8500
```

```python
client = OpenAI(base_url="http://localhost:8500/v1", api_key="sk-ant-...")  # Anthropic 키
resp = client.chat.completions.create(model="claude-sonnet-5", messages=[...])
```

로컬 LLM(vLLM, Ollama의 OpenAI 호환 서버 등)도 같은 방식으로 연결됩니다.

### 차단 모드와 감사 로그

마스킹 대신 **아예 요청을 거부**하려면:

```bash
KPG_ACTION=block   # 탐지 시 400 응답 (어떤 타입이 걸렸는지 메시지에 표시, 값은 미표시)
```

모든 요청의 탐지 결과는 JSONL 감사 로그로 남습니다 — **원문 개인정보 값은 절대 기록되지 않고** 타입·개수만 기록됩니다:

```json
{"ts": "2026-07-23T14:04:07+00:00", "action": "mask", "detections": {"rrn": 1, "phone": 2}}
```

| 환경변수 | 기본값 | 설명 |
|----------|--------|------|
| `KPG_UPSTREAM_BASE_URL` | `https://api.openai.com` | 업스트림 LLM API |
| `KPG_ACTION` | `mask` | `mask`(마스킹 후 전달) / `block`(차단) |
| `KPG_FAIL_MODE` | `closed` | 검사 실패 시 차단(`closed`) / 통과(`open`) |
| `KPG_MASK_MODE` | `format` | 형식 보존(`format`) / 라벨 치환(`placeholder`) |
| `KPG_AUDIT_LOG` | (stdout) | 감사 로그 파일 경로 |

## 방식 3 — Open WebUI 필터 (셀프호스팅 챗 UI)

Open WebUI를 쓴다면 [저장소의 필터 함수](https://github.com/asdqweasdzxcasd/korean-pii-gateway/blob/main/adapters/openwebui/korean_pii_filter.py) 파일 하나로 끝납니다. 관리자 패널 → Functions → 새 함수에 붙여넣으면, 모든 대화가 모델로 가기 전에 마스킹됩니다.

## 방식 4 — Claude Code 플러그인 (개발자)

Claude Code로 코딩하다가 주민번호·API 키가 든 로그를 무심코 붙여넣는 사고를 막습니다:

```
pip install korean-pii        # 시스템 python3에 필요
/plugin marketplace add asdqweasdzxcasd/korean-pii-gateway
/plugin install korean-pii-guard@korean-pii-gateway
```

이후 개인정보가 포함된 프롬프트는 전송 전에 차단되고, 마스킹된 버전이 제안됩니다.

## 무엇이 탐지되나

| 타입 | 오탐 억제 방법 |
|------|----------------|
| 주민등록번호·외국인등록번호 | 생년월일 유효성 + 체크섬 (2020-10 이후 무작위 발급분 대응) |
| 휴대폰·유선 전화번호 | 프리픽스 + 자릿수 |
| 신용카드번호 | Luhn 체크섬 |
| 계좌번호 | 은행명 키워드 근접 문맥 필요 |
| 이메일·여권번호·운전면허번호 | 형식 검증 (여권은 "여권" 키워드 문맥 필요) |
| API 키/시크릿 | sk-, AKIA, ghp_ 등 고유 프리픽스 |

오탐 검증: 일반 한국어 뉴스·코드 텍스트 코퍼스에서 탐지 0건을 테스트로 고정하고 있습니다 (`pytest packages/core/tests/test_corpus.py`).

## 자주 묻는 질문

**Q. 호스팅 서비스는 없나요?** 없고, 만들 계획도 없습니다. 개인정보를 제3자 서버(우리 서버)에 보내는 순간 이 도구의 존재 이유가 사라지기 때문입니다. 전부 여러분의 로컬/사내에서 실행됩니다.

**Q. 이름·주소는 왜 못 잡나요?** 비정형 텍스트라 정규식으로는 오탐 없이 잡기 어렵습니다. NER 기반 탐지는 로드맵에 있습니다.

**Q. 마스킹하면 LLM 답변 품질이 떨어지지 않나요?** 형식 보존 마스킹(`990101-1••••••`)은 "여기 주민번호가 있다"는 문맥을 유지하므로 요약·분석 용도에서는 영향이 거의 없습니다. 개인정보 값 자체가 답변에 필요한 작업이라면 — 그 작업은 애초에 외부 LLM에 보내면 안 되는 작업일 가능성이 높습니다.
