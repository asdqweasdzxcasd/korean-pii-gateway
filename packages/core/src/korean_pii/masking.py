"""타입별 마스킹. 상세 규칙은 Task 7에서 구현."""


def mask_value(type_: str, value: str, mode: str) -> str:
    return "•" * len(value)
