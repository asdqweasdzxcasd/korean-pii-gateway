"""오탐 코퍼스: PII가 없는 일반 한국어·코드 텍스트에서 탐지 0건이어야 한다."""
from pathlib import Path

from korean_pii import detect

CORPUS = Path(__file__).parent / "fixtures" / "corpus_ko.txt"


def test_no_false_positives_on_corpus():
    text = CORPUS.read_text(encoding="utf-8")
    detections = detect(text)
    # 실패 시 원문 값 노출 금지 — 타입·위치만 출력한다
    assert detections == [], [(d.type, d.start) for d in detections]
