"""chat completions 요청 본문 검사·마스킹."""
import copy

from korean_pii import Detection, MaskPolicy, mask


def scan_chat_body(body: dict, mask_mode: str) -> tuple[dict, list[Detection]]:
    scanned = copy.deepcopy(body)
    policy = MaskPolicy(mode=mask_mode)
    detections: list[Detection] = []
    for message in scanned.get("messages", []):
        content = message.get("content")
        if isinstance(content, str):
            result = mask(content, policy)
            message["content"] = result.text
            detections.extend(result.detections)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    result = mask(part.get("text", ""), policy)
                    part["text"] = result.text
                    detections.extend(result.detections)
    return scanned, detections
