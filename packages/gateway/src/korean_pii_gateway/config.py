"""환경변수 기반 설정."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    upstream_base_url: str
    action: str = "mask"        # mask | block
    fail_mode: str = "closed"   # closed | open
    mask_mode: str = "format"   # format | placeholder
    audit_path: str | None = None  # None = stdout

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
