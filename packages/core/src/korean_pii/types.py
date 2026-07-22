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
