# korean-pii-gateway

LLM API로 나가는 요청에서 한국어 개인정보(주민등록번호·전화번호·계좌번호 등)를 탐지해 **마스킹하거나 차단**하는 셀프호스팅 OpenAI 호환 프록시 게이트웨이입니다. 탐지 엔진은 [korean-pii](https://pypi.org/project/korean-pii/)를 사용합니다.

```bash
pip install korean-pii-gateway
uvicorn --factory korean_pii_gateway.app:create_app --port 8500
```

클라이언트는 base URL만 바꾸면 됩니다:

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8500/v1", api_key="sk-...")  # 키는 업스트림으로 패스스루
```

- **BYOK**: `Authorization` 헤더를 업스트림에 그대로 전달하며 게이트웨이는 키를 저장하지 않습니다.
- **감사 로그**: 탐지 타입·개수만 JSONL로 기록 — 원문 개인정보 값은 절대 기록하지 않습니다.
- **fail-closed 기본**: 검사 실패 시 요청을 차단합니다.
- 환경변수(`KPG_UPSTREAM_BASE_URL`, `KPG_ACTION` 등)·Docker 배포·어댑터는 [저장소 문서](https://github.com/asdqweasdzxcasd/korean-pii-gateway)를 참고하세요.

> **중요**: 이 게이트웨이는 보조 방어 계층입니다. 모든 개인정보 탐지를 보장하지 않으며, 법적 컴플라이언스 충족을 보장하지 않습니다.
