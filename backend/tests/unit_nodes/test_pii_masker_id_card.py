import pytest
from safety.l0_filter import _mask_pii as mask_pii


STANDARD_ID_CARDS = [
    ("110101199003071234", "valid_18digit_male"),
    ("11010119900307234X", "valid_18digit_with_X_checksum"),
    ("320102198512150029", "valid_18digit_female"),
    ("510107200108080018", "valid_18digit_young"),
]

NON_ID_CARD_NUMBERS = [
    ("13812345678", "mobile_phone_11digit"),
    ("6222021234567890123", "bank_card_19digit"),
    ("010-12345678", "landline_phone"),
    ("2000-01-01", "date_string"),
    ("123456", "short_number"),
]

MULTIPLE_ID_CARDS_IN_TEXT = [
    "患者的身份证号是110101199003071234，家属的是320102198512150029",
    "110101199003071234 320102198512150029",
]


@pytest.mark.parametrize("id_number,case_id", STANDARD_ID_CARDS)
def test_should_mask_standard_18digit_id_card_to_placeholder(id_number, case_id):
    result = mask_pii(id_number)
    assert result == "[身份证号]"


@pytest.mark.parametrize("non_id_number,case_id", NON_ID_CARD_NUMBERS)
def test_should_preserve_non_id_card_numbers_unchanged(non_id_number, case_id):
    result = mask_pii(non_id_number)
    assert "身份证号" not in result


@pytest.mark.parametrize("input_text", MULTIPLE_ID_CARDS_IN_TEXT)
def test_should_mask_all_id_cards_in_text(input_text):
    result = mask_pii(input_text)
    assert "[身份证号]" in result
    assert "110101199003071234" not in result
    assert "320102198512150029" not in result


def test_should_mask_id_card_and_person_name_embedded_in_text():
    input_text = "患者张三，身份证号110101199003071234，于2026年6月19日就诊"
    result = mask_pii(input_text)
    assert "[身份证号]" in result
    assert "110101199003071234" not in result
