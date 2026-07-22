"""이메일 디텍터."""
import re

from korean_pii.detectors import DETECTORS
from korean_pii.types import Detection

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def find(text: str) -> list[Detection]:
    return [Detection("email", m.start(), m.end(), m.group(0)) for m in _EMAIL.finditer(text)]


DETECTORS["email"] = find
