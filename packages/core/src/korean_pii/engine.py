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
