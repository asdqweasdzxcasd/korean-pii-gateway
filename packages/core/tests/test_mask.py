from korean_pii import MaskPolicy, mask


def test_format_mask_rrn_keeps_birth_and_gender():
    result = mask("주민번호 990101-1234567 입니다")
    assert "990101-1••••••" in result.text
    assert "234567" not in result.text


def test_format_mask_phone_keeps_last4():
    # 규칙: 마지막 4자리만 남기고 마스킹 ("010-1234-5678" → "•••-••••-5678")
    result = mask("연락처 010-1234-5678")
    assert "•••-••••-5678" in result.text


def test_format_mask_email_keeps_prefix_and_domain():
    result = mask("메일 gildong@example.com")
    assert "gi" in result.text and "@example.com" in result.text
    assert "gildong@" not in result.text


def test_placeholder_mode():
    result = mask("주민번호 990101-1234567", MaskPolicy(mode="placeholder"))
    assert "[주민등록번호]" in result.text
    assert "990101" not in result.text


def test_mask_multiple_detections_preserves_surrounding_text():
    result = mask("A 990101-1234567 B 010-1234-5678 C")
    assert result.text.startswith("A ") and result.text.endswith(" C") and " B " in result.text
    assert len(result.detections) == 2
