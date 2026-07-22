"""환경변수 기반 설정."""
import os
from dataclasses import dataclass

_VALID_ACTIONS = {"mask", "block"}
_VALID_FAIL_MODES = {"closed", "open"}
_VALID_MASK_MODES = {"format", "placeholder"}


@dataclass(frozen=True)
class Settings:
    upstream_base_url: str
    action: str = "mask"        # mask | block
    fail_mode: str = "closed"   # closed | open
    mask_mode: str = "format"   # format | placeholder
    audit_path: str | None = None  # None = stdout

    def __post_init__(self) -> None:
        # 오타로 잘못된 값이 설정되면 조용히 무시되지 않고 기동 시점에 즉시 실패해야 한다
        # (예: fail_mode="close" 오타가 인식되지 않은 채 fail-open처럼 동작하는 것을 방지)
        if self.action not in _VALID_ACTIONS:
            raise ValueError(
                f"잘못된 action 값입니다: {self.action!r} (허용값: {sorted(_VALID_ACTIONS)})"
            )
        if self.fail_mode not in _VALID_FAIL_MODES:
            raise ValueError(
                f"잘못된 fail_mode 값입니다: {self.fail_mode!r} (허용값: {sorted(_VALID_FAIL_MODES)})"
            )
        if self.mask_mode not in _VALID_MASK_MODES:
            raise ValueError(
                f"잘못된 mask_mode 값입니다: {self.mask_mode!r} (허용값: {sorted(_VALID_MASK_MODES)})"
            )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            upstream_base_url=os.environ.get(
                "KPG_UPSTREAM_BASE_URL", "https://api.openai.com"
            ).rstrip("/"),
            action=os.environ.get("KPG_ACTION", "mask"),
            fail_mode=os.environ.get("KPG_FAIL_MODE", "closed"),
            mask_mode=os.environ.get("KPG_MASK_MODE", "format"),
            audit_path=os.environ.get("KPG_AUDIT_LOG"),
        )
