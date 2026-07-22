"""JSONL 감사 로거. 원문 PII 값은 절대 기록하지 않는다."""
import json
import sys
from collections import Counter
from datetime import datetime, timezone

from korean_pii import Detection


class AuditLogger:
    def __init__(self, path: str | None):
        self._path = path

    def log(self, action: str, detections: list[Detection]) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "detections": dict(Counter(d.type for d in detections)),
        }
        line = json.dumps(record, ensure_ascii=False)
        if self._path:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        else:
            print(line, file=sys.stdout, flush=True)
