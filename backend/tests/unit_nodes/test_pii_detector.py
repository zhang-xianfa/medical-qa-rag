import pytest
from safety.pii_detector import PIIDetector, PIIResult, _mask_bank_card, _mask_email


@pytest.fixture
def detector():
    return PIIDetector()


def test_detect_id_card_and_mask(detector):
    result = detector.detect_and_mask("我的身份证号是110101199003071234")
    assert "[身份证号]" in result.masked_text
    assert "110101199003071234" not in result.masked_text
    assert any(m.type == "ID_CARD" for m in result.matches)


def test_detect_phone_number_and_mask(detector):
    result = detector.detect_and_mask("联系方式：13812345678")
    assert "[手机号]" in result.masked_text
    assert "13812345678" not in result.masked_text
    assert any(m.type == "PHONE_NUMBER" for m in result.matches)


def test_detect_email_and_mask(detector):
    result = detector.detect_and_mask("邮箱是test@example.com")
    assert "***@" in result.masked_text
    assert "test@example.com" not in result.masked_text
    assert any(m.type == "EMAIL_ADDRESS" for m in result.matches)


def test_detect_person_name_and_mask(detector):
    result = detector.detect_and_mask("我叫张伟，今年30岁")
    assert "[姓名]" in result.masked_text
    assert any(m.type == "PERSON" for m in result.matches)


def test_bank_card_masks_all_but_last_four():
    assert _mask_bank_card("6222021234567890123") == "6222****0123"


def test_bank_card_short_number_masks_all():
    assert _mask_bank_card("12345") == "****"


def test_email_masks_local_part_keeps_domain():
    assert _mask_email("zhangsan@hospital.com") == "zh***@hospital.com"


def test_detect_multiple_pii_types_in_one_text(detector):
    text = "我叫张伟，身份证110101199003071234，手机13812345678"
    result = detector.detect_and_mask(text)
    assert "[姓名]" in result.masked_text
    assert "[身份证号]" in result.masked_text
    assert "[手机号]" in result.masked_text
    types = result.detected_types
    assert "PERSON" in types
    assert "ID_CARD" in types
    assert "PHONE_NUMBER" in types


def test_no_pii_returns_original_text(detector):
    result = detector.detect_and_mask("我今天有点头痛")
    assert result.masked_text == "我今天有点头痛"
    assert result.count == 0


def test_non_id_card_number_preserved(detector):
    result = detector.detect_and_mask("邮编是100010")
    assert "100010" in result.masked_text


def test_pii_result_properties(detector):
    result = detector.detect_and_mask("我叫张三，手机13900139000")
    assert isinstance(result, PIIResult)
    assert result.count == 2
    assert result.detected_types == {"PERSON", "PHONE_NUMBER"}


def test_from_config_loads_without_error():
    d = PIIDetector.from_config()
    assert d is not None
    assert len(d._rules) >= 3
