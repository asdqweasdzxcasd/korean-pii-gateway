from korean_pii import Detection, MaskPolicy, detect, mask


def test_detect_empty_text_returns_empty_list():
    assert detect("") == []


def test_detect_plain_text_returns_empty_list():
    assert detect("안녕하세요. 오늘 날씨가 좋네요.") == []


def test_mask_plain_text_is_identity():
    result = mask("안녕하세요")
    assert result.text == "안녕하세요"
    assert result.detections == []


def test_mask_accepts_policy():
    result = mask("안녕", MaskPolicy(mode="placeholder"))
    assert result.text == "안녕"
