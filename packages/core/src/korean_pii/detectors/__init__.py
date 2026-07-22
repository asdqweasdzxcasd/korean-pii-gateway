"""디텍터 레지스트리. 각 모듈이 여기에 자신을 등록한다."""
from collections.abc import Callable

from korean_pii.types import Detection

DETECTORS: dict[str, Callable[[str], list[Detection]]] = {}

from korean_pii.detectors import phone, rrn  # noqa: E402,F401  디텍터 등록용
