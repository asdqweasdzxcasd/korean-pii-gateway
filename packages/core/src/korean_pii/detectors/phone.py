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
