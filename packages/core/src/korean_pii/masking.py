"""타입별 형식 보존 마스킹과 플레이스홀더."""

_LABELS = {
    "rrn": "[주민등록번호]",
    "phone": "[전화번호]",
    "card": "[카드번호]",
    "email": "[이메일]",
    "account": "[계좌번호]",
    "passport": "[여권번호]",
    "driver_license": "[운전면허번호]",
    "api_key": "[API키]",
}

_SEPARATORS = set("-. @")


def _mask_chars(value: str, keep_head: int = 0, keep_tail: int = 0) -> str:
    # 구분자는 보존하고, 유효 문자만 앞 keep_head개·뒤 keep_tail개 남기고 마스킹
    core = [i for i, ch in enumerate(value) if ch not in _SEPARATORS]
    hide = set(core[keep_head:len(core) - keep_tail if keep_tail else len(core)])
    return "".join("•" if i in hide else ch for i, ch in enumerate(value))


def _mask_email(value: str) -> str:
    local, _, domain = value.partition("@")
    # 로컬파트 유효 문자가 2자 이하면 최소 1자 이상 노출되는 것을 막기 위해 전체 마스킹
    valid_len = sum(1 for ch in local if ch not in _SEPARATORS)
    keep_head = 2 if valid_len > 2 else 0
    return _mask_chars(local, keep_head=keep_head) + "@" + domain


_RULES = {
    "rrn": lambda v: _mask_chars(v, keep_head=7),
    "phone": lambda v: _mask_chars(v, keep_tail=4),
    "card": lambda v: _mask_chars(v, keep_tail=4),
    "email": _mask_email,
    "account": lambda v: _mask_chars(v, keep_tail=3),
    "passport": lambda v: _mask_chars(v, keep_head=2),
    "driver_license": lambda v: _mask_chars(v, keep_head=2),
    "api_key": lambda v: _mask_chars(v, keep_head=6),
}


def mask_value(type_: str, value: str, mode: str) -> str:
    if mode == "placeholder":
        return _LABELS.get(type_, "[개인정보]")
    rule = _RULES.get(type_)
    return rule(value) if rule else "•" * len(value)
