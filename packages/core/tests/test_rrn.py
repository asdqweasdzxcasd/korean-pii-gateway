from korean_pii import detect

# 테스트용 번호는 공개 알고리즘으로 생성한 가상 번호다 (실존 번호 아님).
VALID_WITH_HYPHEN = "990101-1234567"       # 하이픈 있음 → 날짜만 유효하면 탐지
VALID_CHECKSUM = "9901011234563"           # 하이픈 없음, 체크섬 통과 (아래 알고리즘으로 계산)
INVALID_CHECKSUM_BARE = "9901011234567"    # 하이픈 없음, 체크섬 실패 → 미탐지
INVALID_DATE = "991301-1234567"            # 13월 → 미탐지


def _rrn_checksum(digits12: str) -> str:
    weights = (2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5)
    s = sum(int(d) * w for d, w in zip(digits12, weights))
    return str((11 - s % 11) % 10)


def test_fixture_checksum_is_correct():
    # 픽스처 자체 검증: VALID_CHECKSUM 마지막 자리가 실제 체크 자리인지
    assert VALID_CHECKSUM[12] == _rrn_checksum(VALID_CHECKSUM[:12])
    assert INVALID_CHECKSUM_BARE[12] != _rrn_checksum(INVALID_CHECKSUM_BARE[:12])


def test_detects_hyphenated_rrn_without_checksum():
    [d] = detect(f"제 주민번호는 {VALID_WITH_HYPHEN} 입니다")
    assert d.type == "rrn"
    assert d.value == VALID_WITH_HYPHEN


def test_detects_bare_rrn_only_with_valid_checksum():
    [d] = detect(f"번호 {VALID_CHECKSUM} 확인")
    assert d.type == "rrn"
    assert d.value == VALID_CHECKSUM


def test_ignores_bare_rrn_with_bad_checksum():
    assert detect(f"번호 {INVALID_CHECKSUM_BARE} 확인") == []


def test_ignores_invalid_date():
    assert detect(f"번호 {INVALID_DATE} 확인") == []


def test_detects_foreign_registration_number():
    # 성별 자리 5~8 = 외국인등록번호. 하이픈 있으면 날짜 유효성만 요구.
    [d] = detect("외국인등록번호 990101-5234567")
    assert d.type == "rrn"


def test_ignores_invalid_date_feb_30():
    # 2월 30일은 존재하지 않음 → 미탐지
    assert detect("번호 990230-1234567 확인") == []


def test_detects_bare_foreign_rrn_with_old_checksum_correction():
    # 구형 외국인등록번호: 성별자리 5~8, 하이픈 없음, 체크섬은 (standard_check + 2) % 10
    # 픽스처: 990101-512345에서 체크섬을 계산해 +2 보정값을 구성
    digits12 = "990101512345"
    standard_check = _rrn_checksum(digits12)
    old_frn_check = str((int(standard_check) + 2) % 10)
    valid_checksum_old_frn = digits12 + old_frn_check

    [d] = detect(f"번호 {valid_checksum_old_frn} 확인")
    assert d.type == "rrn"
    assert d.value == valid_checksum_old_frn


def test_ignores_bare_foreign_rrn_with_invalid_checksum():
    # 구형 외국인등록번호인데 체크섬이 표준도, +2 보정도 아닌 값 → 미탐지
    digits12 = "990101512345"
    standard_check = _rrn_checksum(digits12)
    old_frn_check = str((int(standard_check) + 2) % 10)
    # 둘 다 아닌 값 선택 (standard_check와 old_frn_check 둘 다 다른 숫자)
    invalid_check = str((int(old_frn_check) + 1) % 10)
    if invalid_check in (standard_check, old_frn_check):
        invalid_check = str((int(invalid_check) + 1) % 10)
    invalid_checksum_old_frn = digits12 + invalid_check

    assert detect(f"번호 {invalid_checksum_old_frn} 확인") == []
