# korean-pii-gateway 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 한국어 PII를 LLM API로 보내기 전에 탐지·마스킹·차단하는 탐지 엔진 + OpenAI 호환 프록시 게이트웨이 + 유통 어댑터 2종.

**Architecture:** 순수 Python 탐지 엔진(`packages/core`, 의존성 0)을 본체로 두고, FastAPI 프록시(`packages/gateway`)와 어댑터(Open WebUI Filter Function, Claude Code 플러그인)가 엔진을 얇게 감싼다. 스펙: `docs/superpowers/specs/2026-07-21-korean-pii-gateway-design.md`.

**Tech Stack:** Python 3.11+, FastAPI, httpx, uvicorn, pytest, hatchling.

## Global Constraints

- Python 3.11 이상.
- `packages/core`(PyPI명 `korean-pii`)는 **런타임 의존성 0** — 표준 라이브러리만 사용.
- `packages/gateway`(PyPI명 `korean-pii-gateway`) 런타임 의존성은 `fastapi`, `httpx`, `uvicorn`만.
- 감사 로그·에러 응답·테스트 출력 어디에도 **원문 PII 값을 기록하지 않는다** (탐지 타입·개수만).
- 커밋 메시지·주석은 한국어. 모든 커밋 메시지 끝에 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- 엔진 검사 실패 시 기본 동작은 fail-closed(차단). `KPG_FAIL_MODE=open`으로만 완화.
- 테스트 실행은 저장소 루트에서 `pytest packages -v`.

## 파일 구조

```
packages/core/
  pyproject.toml
  src/korean_pii/
    __init__.py        # 공개 API re-export
    types.py           # Detection, MaskPolicy, MaskResult
    engine.py          # detect(), mask(), 겹침 해소
    masking.py         # 타입별 형식 보존 마스킹
    detectors/
      __init__.py      # DETECTORS 레지스트리
      rrn.py           # 주민등록번호 + 외국인등록번호
      phone.py         # 휴대폰 + 지역번호
      card.py          # 신용카드 (Luhn)
      contact.py       # 이메일
      contextual.py    # 계좌번호·여권번호 (문맥 조건부) + 운전면허
      secrets.py       # API 키/시크릿
  tests/ (test_rrn.py, test_phone.py, test_card.py, test_contact_secrets.py,
          test_contextual.py, test_mask.py, test_corpus.py, fixtures/corpus_ko.txt)
packages/gateway/
  pyproject.toml
  src/korean_pii_gateway/
    __init__.py
    config.py          # Settings (환경변수)
    audit.py           # JSONL 감사 로거
    scan.py            # chat body 검사/마스킹
    app.py             # create_app() — 프록시 본체
  tests/ (conftest.py, test_health.py, test_proxy.py, test_block_audit.py, test_stream.py)
adapters/
  openwebui/korean_pii_filter.py
  claude-code/
    .claude-plugin/plugin.json
    hooks/hooks.json
    hooks/check_prompt.py
.claude-plugin/marketplace.json
Dockerfile / docker-compose.example.yml / README.md
```

---

### Task 1: core 패키지 스캐폴딩 + 타입 + 엔진 뼈대

**Files:**
- Create: `packages/core/pyproject.toml`, `packages/core/src/korean_pii/__init__.py`, `packages/core/src/korean_pii/types.py`, `packages/core/src/korean_pii/engine.py`, `packages/core/src/korean_pii/detectors/__init__.py`
- Test: `packages/core/tests/test_engine.py`

**Interfaces:**
- Produces: `Detection(type: str, start: int, end: int, value: str)` (frozen dataclass), `MaskPolicy(mode: str = "format", types: set[str] | None = None)`, `MaskResult(text: str, detections: list[Detection])`, `detect(text: str, types: set[str] | None = None) -> list[Detection]`, `mask(text: str, policy: MaskPolicy | None = None) -> MaskResult`. 디텍터 등록 방식: `detectors/__init__.py`의 `DETECTORS: dict[str, Callable[[str], list[Detection]]]`.

- [ ] **Step 1: 패키지 설정과 실패하는 테스트 작성**

`packages/core/pyproject.toml`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "korean-pii"
version = "0.1.0"
description = "한국어 개인정보(PII) 탐지·마스킹 엔진 (의존성 0)"
requires-python = ">=3.11"
license = "MIT"

[tool.hatch.build.targets.wheel]
packages = ["src/korean_pii"]
```

`packages/core/tests/test_engine.py`:
```python
from korean_pii import Detection, MaskPolicy, detect, mask


def test_detect_empty_text_returns_empty_list():
    assert detect("") == []


def test_detect_plain_text_returns_empty_list():
    assert detect("안녕하세요. 오늘 날씨가 좋네요.") == []


def test_mask_plain_text_is_identity():
    result = mask("안녕하세요")
    assert result.text == "안녕하세요"
    assert result.detections == []


def test_mask_accepts_policy():
    result = mask("안녕", MaskPolicy(mode="placeholder"))
    assert result.text == "안녕"
```

- [ ] **Step 2: 실패 확인**

Run: `pip install -e packages/core && pytest packages/core/tests/test_engine.py -v`
Expected: FAIL (`ImportError: cannot import name 'detect'`)

- [ ] **Step 3: 최소 구현**

`packages/core/src/korean_pii/types.py`:
```python
"""엔진 공개 타입 정의."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Detection:
    type: str
    start: int
    end: int
    value: str


@dataclass(frozen=True)
class MaskPolicy:
    mode: str = "format"  # "format"(형식 보존) | "placeholder"
    types: set[str] | None = None  # None = 전체 타입


@dataclass(frozen=True)
class MaskResult:
    text: str
    detections: list[Detection] = field(default_factory=list)
```

`packages/core/src/korean_pii/detectors/__init__.py`:
```python
"""디텍터 레지스트리. 각 모듈이 여기에 자신을 등록한다."""
from collections.abc import Callable

from korean_pii.types import Detection

DETECTORS: dict[str, Callable[[str], list[Detection]]] = {}
```

`packages/core/src/korean_pii/engine.py`:
```python
"""detect/mask 진입점과 겹침 해소."""
from korean_pii.detectors import DETECTORS
from korean_pii.types import Detection, MaskPolicy, MaskResult


def _resolve_overlaps(found: list[Detection]) -> list[Detection]:
    # 시작 위치 오름차순, 같은 시작이면 긴 매치 우선. 겹치면 먼저 채택된 것을 유지.
    kept: list[Detection] = []
    for d in sorted(found, key=lambda d: (d.start, -(d.end - d.start))):
        if all(d.start >= k.end or d.end <= k.start for k in kept):
            kept.append(d)
    return kept


def detect(text: str, types: set[str] | None = None) -> list[Detection]:
    if not text:
        return []
    found: list[Detection] = []
    for name, detector in DETECTORS.items():
        if types is not None and name not in types:
            continue
        found.extend(detector(text))
    return _resolve_overlaps(found)


def mask(text: str, policy: MaskPolicy | None = None) -> MaskResult:
    policy = policy or MaskPolicy()
    detections = detect(text, policy.types)
    if not detections:
        return MaskResult(text=text, detections=[])
    from korean_pii.masking import mask_value  # 순환 참조 방지용 지연 임포트

    out: list[str] = []
    cursor = 0
    for d in detections:
        out.append(text[cursor:d.start])
        out.append(mask_value(d.type, d.value, policy.mode))
        cursor = d.end
    out.append(text[cursor:])
    return MaskResult(text="".join(out), detections=detections)
```

`packages/core/src/korean_pii/__init__.py`:
```python
from korean_pii.engine import detect, mask
from korean_pii.types import Detection, MaskPolicy, MaskResult

__all__ = ["Detection", "MaskPolicy", "MaskResult", "detect", "mask"]
```

`masking.py`는 Task 7에서 구현하지만 지연 임포트가 있으므로 임시 파일을 지금 만든다.

`packages/core/src/korean_pii/masking.py`:
```python
"""타입별 마스킹. 상세 규칙은 Task 7에서 구현."""


def mask_value(type_: str, value: str, mode: str) -> str:
    return "•" * len(value)
```

- [ ] **Step 4: 통과 확인**

Run: `pytest packages/core/tests/test_engine.py -v`
Expected: PASS (4건)

- [ ] **Step 5: 커밋**

```bash
git add packages/core
git commit -m "core: 엔진 뼈대와 공개 타입 추가 (detect/mask, 디텍터 레지스트리)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 주민등록번호·외국인등록번호 디텍터

**Files:**
- Create: `packages/core/src/korean_pii/detectors/rrn.py`
- Modify: `packages/core/src/korean_pii/detectors/__init__.py`
- Test: `packages/core/tests/test_rrn.py`

**Interfaces:**
- Consumes: `Detection`, `DETECTORS` (Task 1)
- Produces: 타입명 `"rrn"`. 탐지 규칙: ①생년월일 유효(세기 코드는 성별 자리 1,2,5,6→1900년대·3,4,7,8→2000년대) ②하이픈 구분자가 있으면 체크섬 없이도 탐지(2020-10 이후 발급분은 무작위 끝자리) ③구분자 없는 13자리 연속 숫자는 체크섬 통과 필수(우연 일치 배제) ④외국인등록번호 구형 체크섬(+2 보정)도 허용.

- [ ] **Step 1: 실패하는 테스트 작성**

`packages/core/tests/test_rrn.py`:
```python
from korean_pii import detect

# 테스트용 번호는 공개 알고리즘으로 생성한 가상 번호다 (실존 번호 아님).
VALID_WITH_HYPHEN = "990101-1234567"       # 하이픈 있음 → 날짜만 유효하면 탐지
VALID_CHECKSUM = "9901011234563"           # 하이픈 없음, 체크섬 통과 (아래 알고리즘으로 계산)
INVALID_CHECKSUM_BARE = "9901011234567"    # 하이픈 없음, 체크섬 실패 → 미탐지
INVALID_DATE = "991301-1234567"            # 13월 → 미탐지


def _rrn_checksum(digits12: str) -> str:
    weights = (2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5)
    s = sum(int(d) * w for d, w in zip(digits12, weights))
    return str((11 - s % 11) % 10)


def test_fixture_checksum_is_correct():
    # 픽스처 자체 검증: VALID_CHECKSUM 마지막 자리가 실제 체크 자리인지
    assert VALID_CHECKSUM[12] == _rrn_checksum(VALID_CHECKSUM[:12])
    assert INVALID_CHECKSUM_BARE[12] != _rrn_checksum(INVALID_CHECKSUM_BARE[:12])


def test_detects_hyphenated_rrn_without_checksum():
    [d] = detect(f"제 주민번호는 {VALID_WITH_HYPHEN} 입니다")
    assert d.type == "rrn"
    assert d.value == VALID_WITH_HYPHEN


def test_detects_bare_rrn_only_with_valid_checksum():
    [d] = detect(f"번호 {VALID_CHECKSUM} 확인")
    assert d.type == "rrn"


def test_ignores_bare_rrn_with_bad_checksum():
    assert detect(f"번호 {INVALID_CHECKSUM_BARE} 확인") == []


def test_ignores_invalid_date():
    assert detect(f"번호 {INVALID_DATE} 확인") == []


def test_detects_foreign_registration_number():
    # 성별 자리 5~8 = 외국인등록번호. 하이픈 있으면 날짜 유효성만 요구.
    [d] = detect("외국인등록번호 990101-5234567")
    assert d.type == "rrn"
```

주의: `VALID_CHECKSUM`/`INVALID_CHECKSUM_BARE` 값은 구현 시 `_rrn_checksum`으로 재계산해 픽스처를 맞춘다 (`test_fixture_checksum_is_correct`가 그 검증이다). 값이 다르면 테스트 상수를 계산 결과로 교체한다.

- [ ] **Step 2: 실패 확인**

Run: `pytest packages/core/tests/test_rrn.py -v`
Expected: `test_fixture_checksum_is_correct`만 PASS 또는 FAIL(상수 조정), 나머지 탐지 테스트 FAIL

- [ ] **Step 3: 구현**

`packages/core/src/korean_pii/detectors/rrn.py`:
```python
"""주민등록번호·외국인등록번호 디텍터."""
import re
from datetime import datetime

from korean_pii.detectors import DETECTORS
from korean_pii.types import Detection

_PATTERN = re.compile(r"(?<!\d)(\d{6})(-?)([1-8]\d{6})(?!\d)")
_WEIGHTS = (2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5)


def _valid_date(front6: str, gender: str) -> bool:
    century = 1900 if gender in "1256" else 2000
    try:
        datetime(century + int(front6[:2]), int(front6[2:4]), int(front6[4:6]))
        return True
    except ValueError:
        return False


def _checksum_ok(digits13: str) -> bool:
    s = sum(int(d) * w for d, w in zip(digits13[:12], _WEIGHTS))
    check = (11 - s % 11) % 10
    # 구형 외국인등록번호는 +2 보정 체크섬을 쓴다
    return int(digits13[12]) in (check, (check + 2) % 10)


def find(text: str) -> list[Detection]:
    found = []
    for m in _PATTERN.finditer(text):
        front, sep, back = m.group(1), m.group(2), m.group(3)
        if not _valid_date(front, back[0]):
            continue
        # 하이픈이 없으면 우연한 13자리 숫자일 가능성이 높아 체크섬을 요구한다
        if not sep and not _checksum_ok(front + back):
            continue
        found.append(Detection("rrn", m.start(), m.end(), m.group(0)))
    return found


DETECTORS["rrn"] = find
```

`packages/core/src/korean_pii/detectors/__init__.py` 끝에 모듈 로드 추가 (이후 Task에서 디텍터를 추가할 때마다 이 임포트 줄에 모듈명을 덧붙인다):
```python
from korean_pii.detectors import rrn  # noqa: E402,F401  디텍터 등록용
```

- [ ] **Step 4: 통과 확인**

Run: `pytest packages/core/tests/test_rrn.py packages/core/tests/test_engine.py -v`
Expected: 전부 PASS (엔진 기존 테스트 회귀 포함)

- [ ] **Step 5: 커밋**

```bash
git add packages/core
git commit -m "core: 주민등록번호·외국인등록번호 디텍터 (생년월일+체크섬 검증)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 전화번호 디텍터

**Files:**
- Create: `packages/core/src/korean_pii/detectors/phone.py`
- Modify: `packages/core/src/korean_pii/detectors/__init__.py` (임포트 줄에 `phone` 추가)
- Test: `packages/core/tests/test_phone.py`

**Interfaces:**
- Consumes: `Detection`, `DETECTORS`
- Produces: 타입명 `"phone"`. 휴대폰(01X) + 유선 지역번호(02, 031~033, 041~044, 051~055, 061~064). 구분자는 `-`, `.`, 공백 허용.

- [ ] **Step 1: 실패하는 테스트 작성**

`packages/core/tests/test_phone.py`:
```python
from korean_pii import detect


def test_detects_mobile_with_hyphen():
    [d] = detect("연락처는 010-1234-5678 입니다")
    assert d.type == "phone"
    assert d.value == "010-1234-5678"


def test_detects_mobile_without_separator():
    [d] = detect("01012345678로 전화주세요")
    assert d.type == "phone"


def test_detects_seoul_landline():
    [d] = detect("사무실 02-777-1234")
    assert d.type == "phone"


def test_ignores_random_digits():
    # 8자리 주문번호 등 오탐 방지
    assert detect("주문번호 20260722 확인") == []


def test_ignores_longer_digit_run():
    # 앞뒤에 숫자가 더 붙으면 전화번호가 아니다
    assert detect("코드 9010123456789991") == []
```

- [ ] **Step 2: 실패 확인**

Run: `pytest packages/core/tests/test_phone.py -v`
Expected: FAIL (탐지 0건)

- [ ] **Step 3: 구현**

`packages/core/src/korean_pii/detectors/phone.py`:
```python
"""한국 전화번호 디텍터 (휴대폰 + 유선)."""
import re

from korean_pii.detectors import DETECTORS
from korean_pii.types import Detection

_MOBILE = re.compile(r"(?<![\d-])01[016789][-. ]?\d{3,4}[-. ]?\d{4}(?![\d-])")
_LANDLINE = re.compile(
    r"(?<![\d-])0(?:2|3[1-3]|4[1-4]|5[1-5]|6[1-4])[-. ]?\d{3,4}[-. ]?\d{4}(?![\d-])"
)


def find(text: str) -> list[Detection]:
    found = []
    for pattern in (_MOBILE, _LANDLINE):
        for m in pattern.finditer(text):
            found.append(Detection("phone", m.start(), m.end(), m.group(0)))
    return found


DETECTORS["phone"] = find
```

- [ ] **Step 4: 통과 확인**

Run: `pytest packages/core -v`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add packages/core
git commit -m "core: 전화번호 디텍터 (휴대폰·유선 지역번호)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 신용카드 디텍터 (Luhn)

**Files:**
- Create: `packages/core/src/korean_pii/detectors/card.py`
- Modify: `packages/core/src/korean_pii/detectors/__init__.py` (임포트 줄에 `card` 추가)
- Test: `packages/core/tests/test_card.py`

**Interfaces:**
- Consumes: `Detection`, `DETECTORS`
- Produces: 타입명 `"card"`. 15~16자리, 4자리 그룹 구분자(`-`, 공백) 허용, Luhn 체크섬 필수.

- [ ] **Step 1: 실패하는 테스트 작성**

`packages/core/tests/test_card.py`:
```python
from korean_pii import detect

LUHN_VALID = "4111 1111 1111 1111"   # 표준 테스트 카드번호 (Luhn 통과)
LUHN_INVALID = "4111 1111 1111 1112"


def test_detects_luhn_valid_card():
    [d] = detect(f"카드번호 {LUHN_VALID} 결제")
    assert d.type == "card"
    assert d.value == LUHN_VALID


def test_detects_hyphenated_card():
    [d] = detect("4111-1111-1111-1111")
    assert d.type == "card"


def test_ignores_luhn_invalid():
    assert detect(f"카드번호 {LUHN_INVALID} 결제") == []


def test_rrn_not_shadowed_by_card(monkeypatch):
    # 주민번호(13자리)와 카드(15~16자리)는 자릿수가 달라 상호 오탐이 없어야 한다
    result = detect("990101-1234567")
    assert [d.type for d in result] == ["rrn"]
```

- [ ] **Step 2: 실패 확인**

Run: `pytest packages/core/tests/test_card.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`packages/core/src/korean_pii/detectors/card.py`:
```python
"""신용카드 번호 디텍터 (Luhn 체크섬)."""
import re

from korean_pii.detectors import DETECTORS
from korean_pii.types import Detection

_PATTERN = re.compile(r"(?<![\d-])\d{4}(?:[- ]?\d{4}){2}[- ]?\d{3,4}(?![\d-])")


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def find(text: str) -> list[Detection]:
    found = []
    for m in _PATTERN.finditer(text):
        digits = re.sub(r"[- ]", "", m.group(0))
        if len(digits) in (15, 16) and _luhn_ok(digits):
            found.append(Detection("card", m.start(), m.end(), m.group(0)))
    return found


DETECTORS["card"] = find
```

- [ ] **Step 4: 통과 확인**

Run: `pytest packages/core -v`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add packages/core
git commit -m "core: 신용카드 디텍터 (Luhn 체크섬 검증)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 이메일 + API 키/시크릿 디텍터

**Files:**
- Create: `packages/core/src/korean_pii/detectors/contact.py`, `packages/core/src/korean_pii/detectors/secrets.py`
- Modify: `packages/core/src/korean_pii/detectors/__init__.py` (임포트 줄에 `contact`, `secrets` 추가)
- Test: `packages/core/tests/test_contact_secrets.py`

**Interfaces:**
- Consumes: `Detection`, `DETECTORS`
- Produces: 타입명 `"email"`, `"api_key"`. api_key 패턴: `sk-...`(OpenAI/Anthropic 계열), `AKIA...`(AWS), `ghp_...`(GitHub).

- [ ] **Step 1: 실패하는 테스트 작성**

`packages/core/tests/test_contact_secrets.py`:
```python
from korean_pii import detect


def test_detects_email():
    [d] = detect("문의는 hong.gildong@example.co.kr 로")
    assert d.type == "email"
    assert d.value == "hong.gildong@example.co.kr"


def test_detects_openai_style_key():
    [d] = detect("OPENAI_API_KEY=sk-proj-abcdefghij1234567890ABCD")
    assert d.type == "api_key"


def test_detects_anthropic_key():
    [d] = detect("sk-ant-api03-abcdefghij1234567890")
    assert d.type == "api_key"


def test_detects_aws_key():
    [d] = detect("AKIAIOSFODNN7EXAMPLE1")  # 21자 아님 주의: AKIA + 16자 = 총 20자
    assert d.type == "api_key"


def test_detects_github_token():
    [d] = detect("ghp_" + "a" * 36)
    assert d.type == "api_key"


def test_ignores_short_sk_word():
    # 'sk-'로 시작해도 20자 미만이면 키가 아니다
    assert detect("sk-test 라는 접두어") == []
```

주의: `test_detects_aws_key`의 픽스처는 `AKIA` + 대문자/숫자 16자여야 한다. `AKIAIOSFODNN7EXAMPLE`(AWS 공식 예제 키, 정확히 20자)를 쓰고 뒤에 붙인 `1`은 제거한다.

- [ ] **Step 2: 실패 확인**

Run: `pytest packages/core/tests/test_contact_secrets.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`packages/core/src/korean_pii/detectors/contact.py`:
```python
"""이메일 디텍터."""
import re

from korean_pii.detectors import DETECTORS
from korean_pii.types import Detection

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def find(text: str) -> list[Detection]:
    return [Detection("email", m.start(), m.end(), m.group(0)) for m in _EMAIL.finditer(text)]


DETECTORS["email"] = find
```

`packages/core/src/korean_pii/detectors/secrets.py`:
```python
"""API 키·시크릿 디텍터 (고유 프리픽스 기반)."""
import re

from korean_pii.detectors import DETECTORS
from korean_pii.types import Detection

_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{17,}\b"),   # OpenAI/Anthropic 계열 (sk- 포함 20자 이상)
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),        # AWS Access Key ID
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),     # GitHub PAT
)


def find(text: str) -> list[Detection]:
    found = []
    for pattern in _PATTERNS:
        for m in pattern.finditer(text):
            found.append(Detection("api_key", m.start(), m.end(), m.group(0)))
    return found


DETECTORS["api_key"] = find
```

- [ ] **Step 4: 통과 확인**

Run: `pytest packages/core -v`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add packages/core
git commit -m "core: 이메일·API 키 디텍터 추가

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: 문맥 조건부 디텍터 (계좌·여권) + 운전면허

**Files:**
- Create: `packages/core/src/korean_pii/detectors/contextual.py`
- Modify: `packages/core/src/korean_pii/detectors/__init__.py` (임포트 줄에 `contextual` 추가)
- Test: `packages/core/tests/test_contextual.py`

**Interfaces:**
- Consumes: `Detection`, `DETECTORS`
- Produces: 타입명 `"account"`(총 10~14자리 하이픈 구분 숫자 + 앞 30자 내 은행/계좌 키워드 필수), `"passport"`(구형 `M12345678`·신형 `M123A4567` + 앞 30자 내 "여권" 키워드 필수), `"driver_license"`(`NN-NN-NNNNNN-NN` 형식, 문맥 불필요).

- [ ] **Step 1: 실패하는 테스트 작성**

`packages/core/tests/test_contextual.py`:
```python
from korean_pii import detect


def test_detects_account_near_bank_keyword():
    [d] = detect("국민은행 123456-04-123456 으로 입금")
    assert d.type == "account"


def test_ignores_account_pattern_without_context():
    # 은행/계좌 키워드가 없으면 하이픈 숫자열은 탐지하지 않는다 (오탐 방지)
    assert detect("일련번호 123456-04-123456 제품") == []


def test_detects_passport_with_context():
    [d] = detect("여권번호 M12345678 확인")
    assert d.type == "passport"


def test_detects_new_format_passport_with_context():
    [d] = detect("여권 M123A4567")
    assert d.type == "passport"


def test_ignores_passport_pattern_without_context():
    assert detect("모델명 M12345678 재고") == []


def test_detects_driver_license_without_context():
    [d] = detect("11-22-123456-78")
    assert d.type == "driver_license"
```

- [ ] **Step 2: 실패 확인**

Run: `pytest packages/core/tests/test_contextual.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`packages/core/src/korean_pii/detectors/contextual.py`:
```python
"""문맥 조건부 디텍터: 계좌번호·여권번호. 운전면허는 형식이 고유해 문맥 불필요."""
import re

from korean_pii.detectors import DETECTORS
from korean_pii.types import Detection

_ACCOUNT = re.compile(r"(?<![\d-])\d{2,6}(?:-\d{2,6}){1,3}(?![\d-])")
_BANK_KEYWORDS = (
    "계좌", "은행", "국민", "신한", "우리", "하나", "농협", "기업",
    "카카오뱅크", "토스", "우체국", "새마을", "수협", "부산", "대구", "SC제일",
)
_PASSPORT = re.compile(r"\b[A-Z](?:\d{8}|\d{3}[A-Z]\d{4})\b")
_PASSPORT_KEYWORDS = ("여권",)
_DRIVER = re.compile(r"(?<![\d-])\d{2}-\d{2}-\d{6}-\d{2}(?![\d-])")
_CONTEXT_WINDOW = 30


def _has_context(text: str, start: int, keywords: tuple[str, ...]) -> bool:
    window = text[max(0, start - _CONTEXT_WINDOW):start]
    return any(k in window for k in keywords)


def find(text: str) -> list[Detection]:
    found = []
    for m in _ACCOUNT.finditer(text):
        digits = m.group(0).replace("-", "")
        if 10 <= len(digits) <= 14 and _has_context(text, m.start(), _BANK_KEYWORDS):
            found.append(Detection("account", m.start(), m.end(), m.group(0)))
    for m in _PASSPORT.finditer(text):
        if _has_context(text, m.start(), _PASSPORT_KEYWORDS):
            found.append(Detection("passport", m.start(), m.end(), m.group(0)))
    for m in _DRIVER.finditer(text):
        found.append(Detection("driver_license", m.start(), m.end(), m.group(0)))
    return found


DETECTORS["contextual"] = find
```

참고: 레지스트리 키는 `"contextual"` 하나지만 Detection의 type은 세 가지다. `detect(types=...)` 필터는 레지스트리 키 기준이므로, 엔진의 타입 필터를 Detection type 기준으로도 거르도록 `engine.py`의 `detect()`를 수정한다:

```python
def detect(text: str, types: set[str] | None = None) -> list[Detection]:
    if not text:
        return []
    found: list[Detection] = []
    for detector in DETECTORS.values():
        found.extend(detector(text))
    if types is not None:
        found = [d for d in found if d.type in types]
    return _resolve_overlaps(found)
```

- [ ] **Step 4: 통과 확인**

Run: `pytest packages/core -v`
Expected: 전부 PASS (기존 테스트 회귀 포함 — `detect(types=...)` 동작 변경 확인)

- [ ] **Step 5: 커밋**

```bash
git add packages/core
git commit -m "core: 계좌·여권(문맥 조건부)·운전면허 디텍터, 타입 필터를 Detection 기준으로 변경

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: 형식 보존 마스킹 + 오탐 코퍼스 테스트

**Files:**
- Modify: `packages/core/src/korean_pii/masking.py` (전체 교체)
- Create: `packages/core/tests/fixtures/corpus_ko.txt`
- Test: `packages/core/tests/test_mask.py`, `packages/core/tests/test_corpus.py`

**Interfaces:**
- Consumes: `mask`, `MaskPolicy` (Task 1), 전체 디텍터
- Produces: `mask_value(type_: str, value: str, mode: str) -> str`. format 모드 규칙 — rrn: 앞 7자리(생년월일+성별) 유지·나머지 `•`, phone: 마지막 4자리만 유지, card: 마지막 4자리만 유지, email: 로컬파트 앞 2자 + 도메인 유지, account: 마지막 3자리 유지, api_key: 앞 6자 유지, passport/driver_license: 앞 2자 유지. 구분자(`-`, `.`, 공백, `@`)는 항상 보존. placeholder 모드: `[주민등록번호]` 등 한글 라벨.

- [ ] **Step 1: 실패하는 테스트 작성**

`packages/core/tests/test_mask.py`:
```python
from korean_pii import MaskPolicy, mask


def test_format_mask_rrn_keeps_birth_and_gender():
    result = mask("주민번호 990101-1234567 입니다")
    assert "990101-1••••••" in result.text
    assert "234567" not in result.text


def test_format_mask_phone_keeps_last4():
    # 규칙: 마지막 4자리만 남기고 마스킹 ("010-1234-5678" → "•••-••••-5678")
    result = mask("연락처 010-1234-5678")
    assert "•••-••••-5678" in result.text


def test_format_mask_email_keeps_prefix_and_domain():
    result = mask("메일 gildong@example.com")
    assert "gi" in result.text and "@example.com" in result.text
    assert "gildong@" not in result.text


def test_placeholder_mode():
    result = mask("주민번호 990101-1234567", MaskPolicy(mode="placeholder"))
    assert "[주민등록번호]" in result.text
    assert "990101" not in result.text


def test_mask_multiple_detections_preserves_surrounding_text():
    result = mask("A 990101-1234567 B 010-1234-5678 C")
    assert result.text.startswith("A ") and result.text.endswith(" C") and " B " in result.text
    assert len(result.detections) == 2
```

`packages/core/tests/test_corpus.py`:
```python
"""오탐 코퍼스: PII가 없는 일반 한국어·코드 텍스트에서 탐지 0건이어야 한다."""
from pathlib import Path

from korean_pii import detect

CORPUS = Path(__file__).parent / "fixtures" / "corpus_ko.txt"


def test_no_false_positives_on_corpus():
    text = CORPUS.read_text(encoding="utf-8")
    detections = detect(text)
    # 실패 시 원문 값 노출 금지 — 타입·위치만 출력한다
    assert detections == [], [(d.type, d.start) for d in detections]
```

`packages/core/tests/fixtures/corpus_ko.txt` (PII 없는 일반 텍스트 — 날짜·주문번호·버전·코드 등 오탐 위험 패턴을 의도적으로 포함해 작성):
```text
2026년 7월 22일 발표된 보고서에 따르면 국내 클라우드 시장은 20% 성장했다.
주문번호 20260722-001 상품이 발송되었습니다. 운송장 6889912345678 조회 바랍니다.
버전 3.11.4 에서 2.7.18 로의 마이그레이션 가이드. 커밋 해시 a1b2c3d4.
회의는 14:30 에 시작하고 참석 인원은 12명이다. 예산은 1,234,567원으로 책정됐다.
좌표 (37.5665, 126.9780) 서울시청. 우편번호 04524 인근.
소스코드: for i in range(20260101, 20261231): process(i)
ISBN 978-89-546-4342-7 도서와 ISSN 1234-5678 저널을 인용했다.
제품 시리얼 SN-2026-0722-991 은 보증 기간 내에 있다.
법인 사업자등록 절차는 3일이 걸리며 수수료는 40,000원이다.
```

주의: 코퍼스의 어떤 줄도 실제 디텍터 패턴(주민번호 형식+유효날짜, Luhn 통과 16자리 등)과 우연히 일치하지 않는지 구현 후 확인하고, 일치가 나오면 **디텍터의 오탐 억제를 먼저 강화**한다(코퍼스를 고치는 게 아니라). 단 ISBN·ISSN처럼 정당한 충돌(예: ISSN `1234-5678`이 계좌 패턴과 유사)은 문맥 조건이 막아주는지 확인용이다.

- [ ] **Step 2: 실패 확인**

Run: `pytest packages/core/tests/test_mask.py packages/core/tests/test_corpus.py -v`
Expected: test_mask FAIL (임시 masking.py는 전체 `•` 치환), test_corpus는 PASS 또는 FAIL(오탐 발견 시 — 발견되면 해당 디텍터 수정)

- [ ] **Step 3: 구현**

`packages/core/src/korean_pii/masking.py` 전체 교체:
```python
"""타입별 형식 보존 마스킹과 플레이스홀더."""

_LABELS = {
    "rrn": "[주민등록번호]",
    "phone": "[전화번호]",
    "card": "[카드번호]",
    "email": "[이메일]",
    "account": "[계좌번호]",
    "passport": "[여권번호]",
    "driver_license": "[운전면허번호]",
    "api_key": "[API키]",
}

_SEPARATORS = set("-. @")


def _mask_chars(value: str, keep_head: int = 0, keep_tail: int = 0) -> str:
    # 구분자는 보존하고, 유효 문자만 앞 keep_head개·뒤 keep_tail개 남기고 마스킹
    core = [i for i, ch in enumerate(value) if ch not in _SEPARATORS]
    hide = set(core[keep_head:len(core) - keep_tail if keep_tail else len(core)])
    return "".join("•" if i in hide else ch for i, ch in enumerate(value))


def _mask_email(value: str) -> str:
    local, _, domain = value.partition("@")
    return _mask_chars(local, keep_head=2) + "@" + domain


_RULES = {
    "rrn": lambda v: _mask_chars(v, keep_head=7),
    "phone": lambda v: _mask_chars(v, keep_tail=4),
    "card": lambda v: _mask_chars(v, keep_tail=4),
    "email": _mask_email,
    "account": lambda v: _mask_chars(v, keep_tail=3),
    "passport": lambda v: _mask_chars(v, keep_head=2),
    "driver_license": lambda v: _mask_chars(v, keep_head=2),
    "api_key": lambda v: _mask_chars(v, keep_head=6),
}


def mask_value(type_: str, value: str, mode: str) -> str:
    if mode == "placeholder":
        return _LABELS.get(type_, "[개인정보]")
    rule = _RULES.get(type_)
    return rule(value) if rule else "•" * len(value)
```

- [ ] **Step 4: 통과 확인**

Run: `pytest packages/core -v`
Expected: 전부 PASS. 코퍼스 테스트에서 오탐이 나오면 해당 디텍터의 경계 조건(lookbehind/lookahead, 문맥 키워드)을 강화하고 다시 실행.

- [ ] **Step 5: 커밋**

```bash
git add packages/core
git commit -m "core: 형식 보존 마스킹·플레이스홀더 구현, 오탐 코퍼스 테스트 추가

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: gateway 패키지 스캐폴딩 + 설정 + /health

**Files:**
- Create: `packages/gateway/pyproject.toml`, `packages/gateway/src/korean_pii_gateway/__init__.py`, `packages/gateway/src/korean_pii_gateway/config.py`, `packages/gateway/src/korean_pii_gateway/app.py`
- Test: `packages/gateway/tests/test_health.py`

**Interfaces:**
- Consumes: 없음 (core는 Task 9부터)
- Produces: `Settings(upstream_base_url: str, action: str, fail_mode: str, mask_mode: str, audit_path: str | None)` — `Settings.from_env()`로 환경변수(`KPG_UPSTREAM_BASE_URL` 기본 `https://api.openai.com`, `KPG_ACTION` mask|block 기본 mask, `KPG_FAIL_MODE` closed|open 기본 closed, `KPG_MASK_MODE` format|placeholder 기본 format, `KPG_AUDIT_LOG` 경로·미설정 시 stdout) 로드. `create_app(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI` — `transport`는 테스트용 주입.

- [ ] **Step 1: 패키지 설정과 실패하는 테스트 작성**

`packages/gateway/pyproject.toml`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "korean-pii-gateway"
version = "0.1.0"
description = "한국어 PII 차단 OpenAI 호환 LLM 프록시 게이트웨이"
requires-python = ">=3.11"
license = "MIT"
dependencies = ["korean-pii", "fastapi>=0.110", "httpx>=0.27", "uvicorn>=0.29"]

[tool.hatch.build.targets.wheel]
packages = ["src/korean_pii_gateway"]

[tool.hatch.metadata]
allow-direct-references = true
```

`packages/gateway/tests/test_health.py`:
```python
from fastapi.testclient import TestClient

from korean_pii_gateway.app import create_app
from korean_pii_gateway.config import Settings


def test_health_returns_ok():
    app = create_app(Settings(upstream_base_url="http://upstream"))
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("KPG_UPSTREAM_BASE_URL", "http://example:8000/")
    monkeypatch.setenv("KPG_ACTION", "block")
    s = Settings.from_env()
    assert s.upstream_base_url == "http://example:8000"  # 끝 슬래시 제거
    assert s.action == "block"
    assert s.fail_mode == "closed"  # 기본값
```

- [ ] **Step 2: 실패 확인**

Run: `pip install -e packages/gateway pytest && pytest packages/gateway -v`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 최소 구현**

`packages/gateway/src/korean_pii_gateway/__init__.py`:
```python
__version__ = "0.1.0"
```

`packages/gateway/src/korean_pii_gateway/config.py`:
```python
"""환경변수 기반 설정."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    upstream_base_url: str
    action: str = "mask"        # mask | block
    fail_mode: str = "closed"   # closed | open
    mask_mode: str = "format"   # format | placeholder
    audit_path: str | None = None  # None = stdout

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            upstream_base_url=os.environ.get(
                "KPG_UPSTREAM_BASE_URL", "https://api.openai.com"
            ).rstrip("/"),
            action=os.environ.get("KPG_ACTION", "mask"),
            fail_mode=os.environ.get("KPG_FAIL_MODE", "closed"),
            mask_mode=os.environ.get("KPG_MASK_MODE", "format"),
            audit_path=os.environ.get("KPG_AUDIT_LOG"),
        )
```

`packages/gateway/src/korean_pii_gateway/app.py`:
```python
"""FastAPI 앱 팩토리."""
import httpx
from fastapi import FastAPI

from korean_pii_gateway.config import Settings


def create_app(
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="korean-pii-gateway")
    app.state.settings = settings
    app.state.client = httpx.AsyncClient(transport=transport, timeout=120.0)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.on_event("shutdown")
    async def shutdown():
        await app.state.client.aclose()

    return app
```

- [ ] **Step 4: 통과 확인**

Run: `pytest packages/gateway -v`
Expected: PASS (2건)

- [ ] **Step 5: 커밋**

```bash
git add packages/gateway
git commit -m "gateway: 패키지 뼈대·환경변수 설정·/health 엔드포인트

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: chat completions 프록시 (마스킹 + BYOK 패스스루)

**Files:**
- Create: `packages/gateway/src/korean_pii_gateway/scan.py`, `packages/gateway/tests/conftest.py`
- Modify: `packages/gateway/src/korean_pii_gateway/app.py`
- Test: `packages/gateway/tests/test_proxy.py`

**Interfaces:**
- Consumes: `korean_pii.mask`, `MaskPolicy` (core), `Settings`, `create_app` (Task 8)
- Produces: `scan_chat_body(body: dict, mask_mode: str) -> tuple[dict, list[Detection]]` — `messages[].content`(문자열·멀티모달 text 파트)를 마스킹한 새 body와 탐지 목록 반환. `POST /v1/chat/completions` 라우트: 검사 → 업스트림 전달 → 응답 스트리밍 반환. `Authorization` 헤더 패스스루.

- [ ] **Step 1: 실패하는 테스트 작성**

`packages/gateway/tests/conftest.py` (가짜 업스트림 — 받은 요청을 그대로 노출):
```python
import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from korean_pii_gateway.app import create_app
from korean_pii_gateway.config import Settings


@pytest.fixture
def upstream_capture():
    captured = {}
    upstream = FastAPI()

    @upstream.post("/v1/chat/completions")
    async def chat(request: Request):
        captured["body"] = await request.json()
        captured["auth"] = request.headers.get("authorization")
        return JSONResponse({"id": "chatcmpl-test", "choices": []})

    captured["app"] = upstream
    return captured


def make_client(upstream_app, **settings_kw):
    settings = Settings(upstream_base_url="http://upstream", **settings_kw)
    transport = httpx.ASGITransport(app=upstream_app)
    app = create_app(settings, transport=transport)
    from fastapi.testclient import TestClient

    return TestClient(app)
```

`packages/gateway/tests/test_proxy.py`:
```python
from tests.conftest import make_client

RRN_TEXT = "내 주민번호는 990101-1234567 이야"


def test_masks_pii_before_forwarding(upstream_capture):
    client = make_client(upstream_capture["app"])
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": RRN_TEXT}]},
        headers={"Authorization": "Bearer sk-user-key-abcdefghij123456"},
    )
    assert resp.status_code == 200
    sent = upstream_capture["body"]["messages"][0]["content"]
    assert "990101-1••••••" in sent
    assert "1234567" not in sent


def test_authorization_header_passthrough(upstream_capture):
    client = make_client(upstream_capture["app"])
    client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "안녕"}]},
        headers={"Authorization": "Bearer test-token"},
    )
    assert upstream_capture["auth"] == "Bearer test-token"


def test_masks_multimodal_text_parts(upstream_capture):
    client = make_client(upstream_capture["app"])
    client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": RRN_TEXT},
                    {"type": "image_url", "image_url": {"url": "http://x/img.png"}},
                ],
            }],
        },
    )
    parts = upstream_capture["body"]["messages"][0]["content"]
    assert "1234567" not in parts[0]["text"]
    assert parts[1]["image_url"]["url"] == "http://x/img.png"  # 비텍스트 파트는 그대로
```

conftest의 `make_client` 임포트가 동작하도록 `packages/gateway/tests/__init__.py` 빈 파일도 생성한다. (pytest rootdir 설정에 따라 `from conftest import make_client`로 바꿔도 된다 — 실행되는 형태를 택한다.)

- [ ] **Step 2: 실패 확인**

Run: `pytest packages/gateway/tests/test_proxy.py -v`
Expected: FAIL (404 — 라우트 없음)

- [ ] **Step 3: 구현**

`packages/gateway/src/korean_pii_gateway/scan.py`:
```python
"""chat completions 요청 본문 검사·마스킹."""
import copy

from korean_pii import Detection, MaskPolicy, mask


def scan_chat_body(body: dict, mask_mode: str) -> tuple[dict, list[Detection]]:
    scanned = copy.deepcopy(body)
    policy = MaskPolicy(mode=mask_mode)
    detections: list[Detection] = []
    for message in scanned.get("messages", []):
        content = message.get("content")
        if isinstance(content, str):
            result = mask(content, policy)
            message["content"] = result.text
            detections.extend(result.detections)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    result = mask(part.get("text", ""), policy)
                    part["text"] = result.text
                    detections.extend(result.detections)
    return scanned, detections
```

`packages/gateway/src/korean_pii_gateway/app.py`의 `create_app` 안, `/health` 라우트 아래에 추가:
```python
    import json as _json

    from fastapi import Request
    from fastapi.responses import JSONResponse, StreamingResponse
    from starlette.background import BackgroundTask

    from korean_pii_gateway.scan import scan_chat_body

    _FORWARD_HEADERS = {"authorization", "content-type", "openai-organization", "openai-project"}
    _SKIP_RESPONSE_HEADERS = {"content-length", "transfer-encoding", "content-encoding", "connection"}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        body = await request.json()
        scanned, detections = scan_chat_body(body, settings.mask_mode)
        headers = {
            k: v for k, v in request.headers.items() if k.lower() in _FORWARD_HEADERS
        }
        upstream_req = app.state.client.build_request(
            "POST",
            settings.upstream_base_url + "/v1/chat/completions",
            content=_json.dumps(scanned, ensure_ascii=False).encode(),
            headers={**headers, "content-type": "application/json"},
        )
        upstream_resp = await app.state.client.send(upstream_req, stream=True)
        resp_headers = {
            k: v
            for k, v in upstream_resp.headers.items()
            if k.lower() not in _SKIP_RESPONSE_HEADERS
        }
        return StreamingResponse(
            upstream_resp.aiter_raw(),
            status_code=upstream_resp.status_code,
            headers=resp_headers,
            background=BackgroundTask(upstream_resp.aclose),
        )
```

- [ ] **Step 4: 통과 확인**

Run: `pytest packages/gateway -v`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add packages/gateway
git commit -m "gateway: chat completions 프록시 — 요청 마스킹, BYOK 헤더 패스스루

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: block 액션 + 감사 로그 + fail-closed

**Files:**
- Create: `packages/gateway/src/korean_pii_gateway/audit.py`
- Modify: `packages/gateway/src/korean_pii_gateway/app.py`
- Test: `packages/gateway/tests/test_block_audit.py`

**Interfaces:**
- Consumes: `scan_chat_body`, `Settings`, `create_app`
- Produces: `AuditLogger(path: str | None)` — `.log(action: str, detections: list[Detection]) -> None`, JSONL 한 줄에 `{"ts": ISO8601, "action": "mask"|"block"|"pass"|"scan_failed", "detections": {타입: 개수}}` 기록 (원문 값 절대 미기록). block 시 응답: HTTP 400, OpenAI 에러 형식 `{"error": {"message": ..., "type": "invalid_request_error", "code": "pii_detected", "param": null}}` — message에 탐지 타입 나열(값은 없음). 검사 예외 시 fail_mode에 따라 400(`code: "pii_scan_failed"`) 또는 원본 그대로 전달.

- [ ] **Step 1: 실패하는 테스트 작성**

`packages/gateway/tests/test_block_audit.py`:
```python
import json

from tests.conftest import make_client

RRN_TEXT = "주민번호 990101-1234567"


def test_block_action_returns_openai_style_error(upstream_capture):
    client = make_client(upstream_capture["app"], action="block")
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
    client = make_client(upstream_capture["app"], audit_path=str(audit_file))
    client.post(
        "/v1/chat/completions",
        json={"model": "m", "messages": [{"role": "user", "content": RRN_TEXT}]},
    )
    line = json.loads(audit_file.read_text(encoding="utf-8").splitlines()[0])
    assert line["action"] == "mask"
    assert line["detections"] == {"rrn": 1}
    assert "990101" not in json.dumps(line)


def test_scan_failure_fail_closed(upstream_capture, monkeypatch):
    client = make_client(upstream_capture["app"])  # fail_mode 기본 closed
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
    client = make_client(upstream_capture["app"], fail_mode="open")
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
```

monkeypatch가 동작하도록 `app.py`는 `scan_chat_body`를 **모듈 최상위에서 임포트**해 `korean_pii_gateway.app.scan_chat_body`로 참조되게 한다 (Task 9의 함수 내부 임포트를 최상위로 이동).

- [ ] **Step 2: 실패 확인**

Run: `pytest packages/gateway/tests/test_block_audit.py -v`
Expected: FAIL

- [ ] **Step 3: 구현**

`packages/gateway/src/korean_pii_gateway/audit.py`:
```python
"""JSONL 감사 로거. 원문 PII 값은 절대 기록하지 않는다."""
import json
import sys
from collections import Counter
from datetime import datetime, timezone

from korean_pii import Detection


class AuditLogger:
    def __init__(self, path: str | None):
        self._path = path

    def log(self, action: str, detections: list[Detection]) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "detections": dict(Counter(d.type for d in detections)),
        }
        line = json.dumps(record, ensure_ascii=False)
        if self._path:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        else:
            print(line, file=sys.stdout, flush=True)
```

`app.py` 수정 — 최상위 임포트로 정리하고 라우트 본문을 다음으로 교체:
```python
"""FastAPI 앱 팩토리."""
import json as _json

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from korean_pii_gateway.audit import AuditLogger
from korean_pii_gateway.config import Settings
from korean_pii_gateway.scan import scan_chat_body

_FORWARD_HEADERS = {"authorization", "content-type", "openai-organization", "openai-project"}
_SKIP_RESPONSE_HEADERS = {"content-length", "transfer-encoding", "content-encoding", "connection"}


def _error(message: str, code: str) -> dict:
    return {"error": {"message": message, "type": "invalid_request_error",
                      "code": code, "param": None}}


def create_app(
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="korean-pii-gateway")
    app.state.settings = settings
    app.state.client = httpx.AsyncClient(transport=transport, timeout=120.0)
    audit = AuditLogger(settings.audit_path)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        body = await request.json()
        try:
            scanned, detections = scan_chat_body(body, settings.mask_mode)
        except Exception:
            audit.log("scan_failed", [])
            if settings.fail_mode == "closed":
                return JSONResponse(
                    status_code=400,
                    content=_error("PII 검사에 실패해 요청을 차단했습니다 (fail-closed).",
                                   "pii_scan_failed"),
                )
            scanned, detections = body, []
        if detections and settings.action == "block":
            types = sorted({d.type for d in detections})
            audit.log("block", detections)
            return JSONResponse(
                status_code=400,
                content=_error(f"개인정보가 탐지되어 차단했습니다: {', '.join(types)}",
                               "pii_detected"),
            )
        audit.log("mask" if detections else "pass", detections)
        headers = {k: v for k, v in request.headers.items() if k.lower() in _FORWARD_HEADERS}
        upstream_req = app.state.client.build_request(
            "POST",
            settings.upstream_base_url + "/v1/chat/completions",
            content=_json.dumps(scanned, ensure_ascii=False).encode(),
            headers={**headers, "content-type": "application/json"},
        )
        upstream_resp = await app.state.client.send(upstream_req, stream=True)
        resp_headers = {k: v for k, v in upstream_resp.headers.items()
                        if k.lower() not in _SKIP_RESPONSE_HEADERS}
        return StreamingResponse(
            upstream_resp.aiter_raw(),
            status_code=upstream_resp.status_code,
            headers=resp_headers,
            background=BackgroundTask(upstream_resp.aclose),
        )

    @app.on_event("shutdown")
    async def shutdown():
        await app.state.client.aclose()

    return app
```

- [ ] **Step 4: 통과 확인**

Run: `pytest packages/gateway -v`
Expected: 전부 PASS (Task 9 테스트 회귀 포함)

- [ ] **Step 5: 커밋**

```bash
git add packages/gateway
git commit -m "gateway: block 액션·JSONL 감사 로그·fail-closed 처리

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: 스트리밍(SSE) 패스스루 검증

**Files:**
- Test: `packages/gateway/tests/test_stream.py`

**Interfaces:**
- Consumes: `create_app`, `Settings`, conftest 패턴 (Task 9~10). 구현 변경은 없을 수도 있다 — StreamingResponse가 이미 raw 패스스루이므로, 이 Task는 SSE 무결성의 **회귀 방지 테스트**를 고정하는 것이 목적.

- [ ] **Step 1: 실패(또는 통과)하는 테스트 작성**

`packages/gateway/tests/test_stream.py`:
```python
import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from tests.conftest import make_client

SSE_CHUNKS = [
    b'data: {"choices":[{"delta":{"content":"\xec\x95\x88"}}]}\n\n',
    b'data: {"choices":[{"delta":{"content":"\xeb\x85\x95"}}]}\n\n',
    b"data: [DONE]\n\n",
]


@pytest.fixture
def sse_upstream():
    upstream = FastAPI()

    @upstream.post("/v1/chat/completions")
    async def chat():
        async def gen():
            for chunk in SSE_CHUNKS:
                yield chunk

        return StreamingResponse(gen(), media_type="text/event-stream")

    return upstream


def test_sse_bytes_pass_through_unmodified(sse_upstream):
    client = make_client(sse_upstream)
    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={"model": "m", "stream": True,
              "messages": [{"role": "user", "content": "안녕"}]},
    ) as resp:
        received = b"".join(resp.iter_bytes())
    assert received == b"".join(SSE_CHUNKS)
    assert resp.headers["content-type"].startswith("text/event-stream")
```

- [ ] **Step 2: 실행**

Run: `pytest packages/gateway/tests/test_stream.py -v`
Expected: PASS면 구현 변경 없이 Step 5로. FAIL이면 원인(헤더 필터·청크 분할)을 고쳐서 통과시킨다.

- [ ] **Step 3~4: (필요 시) 수정 후 전체 회귀 확인**

Run: `pytest packages -v`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add packages/gateway
git commit -m "gateway: SSE 스트리밍 패스스루 회귀 테스트 고정

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: Docker + README (한글)

**Files:**
- Create: `Dockerfile`, `docker-compose.example.yml`, `README.md`, `.gitignore`, `.dockerignore`

**Interfaces:**
- Consumes: 완성된 두 패키지
- Produces: `docker build` 가능한 이미지 (uvicorn으로 게이트웨이 실행, 포트 8500), 한글 README (제품 소개, "보조 방어 계층" 명시, 설치 3종 — pip/Docker/compose, 환경변수 표, 벤치마크 표 자리).

- [ ] **Step 1: 파일 작성**

`.gitignore`:
```
__pycache__/
*.egg-info/
.pytest_cache/
dist/
.venv/
```

`.dockerignore`:
```
.git
docs
adapters
**/__pycache__
**/.pytest_cache
```

`Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY packages/core /app/packages/core
COPY packages/gateway /app/packages/gateway
RUN pip install --no-cache-dir /app/packages/core /app/packages/gateway
EXPOSE 8500
# 감사 로그는 기본 stdout — docker logs로 수집
CMD ["uvicorn", "--factory", "korean_pii_gateway.app:create_app", "--host", "0.0.0.0", "--port", "8500"]
```

`docker-compose.example.yml`:
```yaml
services:
  korean-pii-gateway:
    build: .
    ports:
      - "8500:8500"
    environment:
      KPG_UPSTREAM_BASE_URL: https://api.openai.com   # Claude는 Anthropic OpenAI 호환 엔드포인트로 교체
      KPG_ACTION: mask        # mask | block
      KPG_FAIL_MODE: closed   # closed | open
      KPG_MASK_MODE: format   # format | placeholder
```

`README.md` — 다음 섹션을 실제 내용으로 작성한다 (개조식 금지, 완성 문장):
1. 한 줄 소개: "LLM API로 나가는 요청에서 한국어 개인정보(주민등록번호·전화번호·계좌번호 등)를 탐지해 마스킹·차단하는 셀프호스팅 게이트웨이"
2. **중요 고지**: 보조 방어 계층이며 컴플라이언스를 보장하지 않음 (탐지 누락 가능)
3. 빠른 시작: `pip install korean-pii-gateway` + uvicorn 실행, Docker 실행, compose 예시. 클라이언트는 base URL만 `http://localhost:8500/v1`로 변경 (OpenAI SDK 예제 코드 포함)
4. 엔진 단독 사용: `pip install korean-pii` + `detect`/`mask` 예제 코드
5. 탐지 타입 표 (스펙의 표 재사용) + 검증 방식 (체크섬·문맥 조건)
6. 환경변수 표 (KPG_* 5종)
7. 벤치마크 섹션: 오탐 코퍼스 테스트 설명 + "재현: `pytest packages/core/tests/test_corpus.py`" (수치 표는 코퍼스 확장 후 채움)
8. 어댑터 안내 자리 (Task 13~14 후 링크 추가)

- [ ] **Step 2: 빌드·실행 검증**

Run: `docker build -t korean-pii-gateway . && docker run -d --rm -p 8500:8500 --name kpg-test korean-pii-gateway && sleep 3 && curl -s localhost:8500/health && docker stop kpg-test`
Expected: `{"status":"ok"}`

- [ ] **Step 3: 커밋**

```bash
git add Dockerfile docker-compose.example.yml README.md .gitignore .dockerignore
git commit -m "배포: Dockerfile·compose 예시·한글 README

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 13: Open WebUI Filter Function 어댑터

**Files:**
- Create: `adapters/openwebui/korean_pii_filter.py`
- Test: `packages/core/tests/test_openwebui_adapter.py` (엔진 테스트 환경 재사용)

**Interfaces:**
- Consumes: `korean_pii.mask`, `MaskPolicy`
- Produces: Open WebUI Filter Function 규격 클래스 `Filter` — `inlet(body: dict) -> dict`가 `messages[].content` 문자열을 마스킹. 프론트매터 docstring에 `title`/`requirements: korean-pii` 명시 (openwebui.com 등록 규격).

- [ ] **Step 1: 실패하는 테스트 작성**

`packages/core/tests/test_openwebui_adapter.py`:
```python
import importlib.util
from pathlib import Path

ADAPTER = Path(__file__).parents[3] / "adapters" / "openwebui" / "korean_pii_filter.py"


def _load_filter():
    spec = importlib.util.spec_from_file_location("korean_pii_filter", ADAPTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Filter()


def test_inlet_masks_korean_pii():
    f = _load_filter()
    body = {"messages": [{"role": "user", "content": "주민번호 990101-1234567"}]}
    out = f.inlet(body)
    assert "1234567" not in out["messages"][0]["content"]
    assert "990101-1••••••" in out["messages"][0]["content"]


def test_inlet_passes_non_string_content():
    f = _load_filter()
    body = {"messages": [{"role": "user", "content": None}]}
    assert f.inlet(body) == body
```

- [ ] **Step 2: 실패 확인**

Run: `pytest packages/core/tests/test_openwebui_adapter.py -v`
Expected: FAIL (파일 없음)

- [ ] **Step 3: 구현**

`adapters/openwebui/korean_pii_filter.py`:
```python
"""
title: Korean PII Filter
author: korean-pii-gateway
description: 한국어 개인정보(주민등록번호·전화번호·계좌번호 등)를 모델로 보내기 전에 마스킹합니다.
requirements: korean-pii
version: 0.1.0
license: MIT
"""
from pydantic import BaseModel

from korean_pii import MaskPolicy, mask


class Filter:
    class Valves(BaseModel):
        # format: 형식 보존 마스킹, placeholder: [주민등록번호] 라벨 치환
        mask_mode: str = "format"

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: dict | None = None) -> dict:
        policy = MaskPolicy(mode=self.valves.mask_mode)
        for message in body.get("messages", []):
            content = message.get("content")
            if isinstance(content, str):
                message["content"] = mask(content, policy).text
        return body
```

참고: Open WebUI 실행 환경에는 pydantic이 내장되어 있다. 로컬 테스트 환경에는 gateway 의존성(fastapi)으로 이미 pydantic이 설치돼 있으므로 별도 설치 불필요.

- [ ] **Step 4: 통과 확인**

Run: `pytest packages/core/tests/test_openwebui_adapter.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add adapters/openwebui packages/core/tests/test_openwebui_adapter.py
git commit -m "어댑터: Open WebUI Filter Function (한국어 PII 마스킹)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 14: Claude Code 플러그인 어댑터 + 마켓플레이스

**Files:**
- Create: `.claude-plugin/marketplace.json`, `adapters/claude-code/.claude-plugin/plugin.json`, `adapters/claude-code/hooks/hooks.json`, `adapters/claude-code/hooks/check_prompt.py`
- Test: `packages/core/tests/test_claude_code_adapter.py`

**Interfaces:**
- Consumes: `korean_pii.detect`, `mask`
- Produces: `UserPromptSubmit` 훅 — stdin JSON(`{"prompt": "..."}`)을 읽어 PII 탐지 시 `{"decision": "block", "reason": "<탐지 타입 + 마스킹된 제안문>"}`을 stdout으로 출력(차단), 미탐지 시 출력 없이 exit 0(통과). reason에 원문 PII 값 미포함(마스킹본만).

- [ ] **Step 1: 실패하는 테스트 작성**

`packages/core/tests/test_claude_code_adapter.py`:
```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `pytest packages/core/tests/test_claude_code_adapter.py -v`
Expected: FAIL (파일 없음)

- [ ] **Step 3: 구현**

`adapters/claude-code/hooks/check_prompt.py`:
```python
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
```

`adapters/claude-code/.claude-plugin/plugin.json`:
```json
{
  "name": "korean-pii-guard",
  "version": "0.1.0",
  "description": "프롬프트의 한국어 개인정보(주민등록번호·전화번호 등)를 전송 전에 탐지·차단합니다. korean-pii 패키지 필요: pip install korean-pii"
}
```

`adapters/claude-code/hooks/hooks.json`:
```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/check_prompt.py"
          }
        ]
      }
    ]
  }
}
```

`.claude-plugin/marketplace.json` (저장소 루트 — 이 레포 자체가 마켓플레이스):
```json
{
  "name": "korean-pii-gateway",
  "owner": { "name": "asdqweasdzxcasd" },
  "plugins": [
    {
      "name": "korean-pii-guard",
      "source": "./adapters/claude-code",
      "description": "한국어 개인정보를 Claude에 보내기 전에 탐지·차단하는 훅"
    }
  ]
}
```

주의: hooks.json의 정확한 스키마(플러그인 훅 등록 형식)와 `UserPromptSubmit` 차단 JSON 규격은 구현 시점에 공식 문서(code.claude.com/docs 훅·플러그인 페이지)로 검증한다. 차단 대신 `additionalContext`로 경고만 넣는 옵션이 필요하면 V1 이후에 valve로 추가한다.

- [ ] **Step 4: 통과 확인 + 실기 검증**

Run: `pytest packages/core/tests/test_claude_code_adapter.py -v`
Expected: PASS

실기 검증(로컬): `claude` 세션에서 `/plugin marketplace add /home/asd/dev/korean-pii-gateway` → `/plugin install korean-pii-guard@korean-pii-gateway` → PII 포함 프롬프트 입력 시 차단 메시지 확인.

- [ ] **Step 5: 커밋 + README 어댑터 섹션 갱신**

README의 어댑터 자리(Task 12의 8번 섹션)에 Open WebUI·Claude Code 설치법을 채운 뒤:
```bash
git add .claude-plugin adapters/claude-code packages/core/tests/test_claude_code_adapter.py README.md
git commit -m "어댑터: Claude Code 플러그인(UserPromptSubmit 훅)과 마켓플레이스 등록

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## 완료 기준

- `pytest packages -v` 전체 통과 (오탐 코퍼스 0건 포함)
- `docker build` + `/health` 응답 확인
- 어댑터 2종 테스트 통과, Claude Code 플러그인 로컬 실기 확인
- README에 "보조 방어 계층" 고지 및 설치법 3종 + 어댑터 2종 기재
