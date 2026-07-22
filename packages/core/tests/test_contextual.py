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


def test_phone_not_misclassified_as_account_near_bank_keyword():
    # 은행 키워드 근처의 전화번호는 phone이어야 하고 account로 오분류되면 안 됨
    detections = detect("국민은행 고객센터 010-1234-5678로 문의주세요")
    types = [d.type for d in detections]
    assert types == ["phone"]


def test_driver_license_not_misclassified_as_account_near_bank_keyword():
    # 은행 키워드 근처의 운전면허는 driver_license이어야 하고 account로 오분류되면 안 됨
    detections = detect("국민은행 11-22-123456-78 문의")
    types = [d.type for d in detections]
    assert types == ["driver_license"]
