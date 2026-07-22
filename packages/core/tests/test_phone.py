from korean_pii import detect


def test_detects_mobile_with_hyphen():
    [d] = detect("연락처는 010-1234-5678 입니다")
    assert d.type == "phone"
    assert d.value == "010-1234-5678"


def test_detects_mobile_without_separator():
    [d] = detect("01012345678로 전화주세요")
    assert d.type == "phone"


def test_detects_seoul_landline():
    [d] = detect("사무실 02-777-1234")
    assert d.type == "phone"


def test_ignores_random_digits():
    # 8자리 주문번호 등 오탐 방지
    assert detect("주문번호 20260722 확인") == []


def test_ignores_longer_digit_run():
    # 앞뒤에 숫자가 더 붙으면 전화번호가 아니다
    assert detect("코드 9010123456789991") == []
