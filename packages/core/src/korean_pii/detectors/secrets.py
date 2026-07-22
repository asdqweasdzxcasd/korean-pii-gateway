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
