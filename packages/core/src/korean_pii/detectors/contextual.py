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
