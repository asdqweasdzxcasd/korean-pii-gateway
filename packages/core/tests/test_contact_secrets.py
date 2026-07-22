from korean_pii import detect


def test_detects_email():
    [d] = detect("문의는 hong.gildong@example.co.kr 로")
    assert d.type == "email"
    assert d.value == "hong.gildong@example.co.kr"


def test_detects_openai_style_key():
    [d] = detect("OPENAI_API_KEY=sk-proj-abcdefghij1234567890ABCD")
    assert d.type == "api_key"


def test_detects_anthropic_key():
    [d] = detect("sk-ant-api03-abcdefghij1234567890")
    assert d.type == "api_key"


def test_detects_aws_key():
    [d] = detect("AKIAIOSFODNN7EXAMPLE")
    assert d.type == "api_key"


def test_detects_github_token():
    [d] = detect("ghp_" + "a" * 36)
    assert d.type == "api_key"


def test_ignores_short_sk_word():
    # 'sk-'로 시작해도 20자 미만이면 키가 아니다
    assert detect("sk-test 라는 접두어") == []
