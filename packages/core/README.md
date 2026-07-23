# korean-pii

한국어 개인정보(PII)를 탐지·마스킹하는 순수 Python 엔진입니다. **런타임 의존성이 없습니다** (표준 라이브러리만 사용).

주민등록번호·외국인등록번호(체크섬 검증), 전화번호, 신용카드번호(Luhn), 이메일, 계좌번호·여권번호(문맥 조건부), 운전면허번호, API 키/시크릿을 정규식 + 유효성 검증으로 탐지해 오탐을 억제합니다.

```bash
pip install korean-pii
```

```python
from korean_pii import detect, mask, MaskPolicy

text = "주민번호 990101-1234567, 연락처 010-1234-5678"

for d in detect(text):
    print(d.type, d.start, d.end)   # rrn 5 19 / phone 26 39

print(mask(text).text)
# 주민번호 990101-1••••••, 연락처 •••-••••-5678

print(mask(text, MaskPolicy(mode="placeholder")).text)
# 주민번호 [주민등록번호], 연락처 [전화번호]
```

> **중요**: 이 라이브러리는 보조 방어 계층입니다. 모든 개인정보 탐지를 보장하지 않으며, 법적 컴플라이언스 충족을 보장하지 않습니다.

이 엔진을 감싼 OpenAI 호환 LLM 프록시 게이트웨이와 Open WebUI·Claude Code 어댑터는 [저장소](https://github.com/asdqweasdzxcasd/korean-pii-gateway)를 참고하세요.
