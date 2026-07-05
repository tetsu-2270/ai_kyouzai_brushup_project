import pytest

from src.models import requirements_from_dict


def _valid_requirements() -> dict:
    return {
        "theme": "テーマ",
        "target_audience": "対象読者",
        "goal": "ゴール",
        "reader_problem": "悩み",
        "promised_value": "約束する価値",
        "tone": "やさしいトーン",
        "output_style": "PDF",
        "page_count": 5,
        "must_include": ["含める要素A"],
        "must_not_include": ["避ける表現A"],
    }


def test_requirements_from_dict_parses_all_fields():
    requirements = requirements_from_dict(_valid_requirements())

    assert requirements.theme == "テーマ"
    assert requirements.page_count == 5
    assert requirements.must_include == ["含める要素A"]
    assert requirements.must_not_include == ["避ける表現A"]


def test_requirements_from_dict_defaults_when_fields_missing():
    requirements = requirements_from_dict({})

    assert requirements.theme == ""
    assert requirements.page_count is None
    assert requirements.must_include == []


@pytest.mark.parametrize(
    "field_name", ["theme", "target_audience", "goal", "reader_problem", "promised_value", "tone", "output_style"]
)
def test_requirements_string_field_must_be_string(field_name):
    data = _valid_requirements()
    data[field_name] = 123

    with pytest.raises(ValueError, match=f"{field_name}は文字列で指定してください"):
        requirements_from_dict(data)


@pytest.mark.parametrize("field_name", ["must_include", "must_not_include"])
def test_requirements_list_field_must_be_list_of_strings(field_name):
    data = _valid_requirements()
    data[field_name] = [123]

    with pytest.raises(ValueError, match=f"{field_name}\\[0\\]は文字列で指定してください"):
        requirements_from_dict(data)


def test_requirements_page_count_must_be_int():
    data = _valid_requirements()
    data["page_count"] = "5"

    with pytest.raises(ValueError, match="page_countは整数で指定してください"):
        requirements_from_dict(data)
