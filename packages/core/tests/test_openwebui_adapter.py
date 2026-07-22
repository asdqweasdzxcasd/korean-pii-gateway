import importlib.util
from pathlib import Path

ADAPTER = Path(__file__).parents[3] / "adapters" / "openwebui" / "korean_pii_filter.py"


def _load_filter():
    spec = importlib.util.spec_from_file_location("korean_pii_filter", ADAPTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Filter()


def test_inlet_masks_korean_pii():
    f = _load_filter()
    body = {"messages": [{"role": "user", "content": "주민번호 990101-1234567"}]}
    out = f.inlet(body)
    assert "1234567" not in out["messages"][0]["content"]
    assert "990101-1••••••" in out["messages"][0]["content"]


def test_inlet_passes_non_string_content():
    f = _load_filter()
    body = {"messages": [{"role": "user", "content": None}]}
    assert f.inlet(body) == body
