from korean_pii import detect


def test_detects_account_near_bank_keyword():
    [d] = detect("국민은행 123456-04-123456 으로 입금")
    assert d.type == "account"


def test_ignores_account_pattern_without_context():
    # 은행/계좌 키워드가 없으면 하이픈 숫자열은 탐지하지 않는다 (오탐 방지)
    assert detect("일련번호 123456-04-123456 제품") == []


def test_detects_passport_with_context():
    [d] = detect("여권번호 M12345678 확인")
    assert d.type == "passport"


def test_detects_new_format_passport_with_context():
    [d] = detect("여권 M123A4567")
    assert d.type == "passport"


def test_ignores_passport_pattern_without_context():
    assert detect("모델명 M12345678 재고") == []


def test_detects_driver_license_without_context():
    [d] = detect("11-22-123456-78")
    assert d.type == "driver_license"
