from korean_pii import detect

LUHN_VALID = "4111 1111 1111 1111"   # 표준 테스트 카드번호 (Luhn 통과)
LUHN_INVALID = "4111 1111 1111 1112"


def test_detects_luhn_valid_card():
    [d] = detect(f"카드번호 {LUHN_VALID} 결제")
    assert d.type == "card"
    assert d.value == LUHN_VALID


def test_detects_hyphenated_card():
    [d] = detect("4111-1111-1111-1111")
    assert d.type == "card"


def test_ignores_luhn_invalid():
    assert detect(f"카드번호 {LUHN_INVALID} 결제") == []


def test_rrn_not_shadowed_by_card(monkeypatch):
    # 주민번호(13자리)와 카드(15~16자리)는 자릿수가 달라 상호 오탐이 없어야 한다
    result = detect("990101-1234567")
    assert [d.type for d in result] == ["rrn"]
