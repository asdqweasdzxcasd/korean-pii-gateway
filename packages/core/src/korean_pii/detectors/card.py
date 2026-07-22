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
