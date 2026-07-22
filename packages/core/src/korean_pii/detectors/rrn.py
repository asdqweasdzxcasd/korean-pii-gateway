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
