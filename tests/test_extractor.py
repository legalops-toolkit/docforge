import pytest

from src.core.exceptions import ExtractionError
from src.extractor.extractor import ExtractionResult, parse_amount


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Разряды разделены пробелом — основной формат судебных актов.
        ("500 000", 500000.0),
        ("1 234 567,89", 1234567.89),
        # Неразрывный пробел: копируется из документов чаще обычного.
        ("500 000", 500000.0),
        ("45 300.50", 45300.50),
        ("500000", 500000.0),
    ],
)
def test_parse_amount_valid(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "  ",
        "не указана",
        # Ноль и отрицательные значения /generate/* всё равно не примут
        # (там claim_amount строго больше нуля), поэтому наружу отдаётся None,
        # а не число: пустое поле в иске лучше нулевой суммы.
        "0",
        "0,00",
    ],
)
def test_parse_amount_invalid_returns_none(raw):
    assert parse_amount(raw) is None


def test_extract_entities(extractor, sample_ruling_text):
    result = extractor.extract(sample_ruling_text)
    assert isinstance(result, ExtractionResult)
    assert result.case_number == "А40-12345/2024"
    assert result.court == "Арбитражный суд города Москвы"
    assert result.claim_amount != "Не указана"
    # Строка остаётся как в тексте, рядом — то же число для /generate/*.
    assert result.claim_amount == "500 000"
    assert result.claim_amount_value == 500000.0


def test_extract_entities_from_general_jurisdiction_ruling(extractor):
    """Решение суда общей юрисдикции, а не арбитража.

    Раньше на таком тексте extract() не находил ни суда (паттерн начинался со
    слова «Арбитражный»), ни номера дела (требовался код суда из кириллических
    букв перед цифрами) — то есть половина российских судебных актов
    возвращала пустой результат по всем regex-полям сразу.
    """
    text = (
        "Замоскворецкий районный суд города Москвы в составе судьи Ёлкиной А.Б. "
        'рассмотрел дело № 2-1234/2024 по иску ООО "Ромашка" '
        "к Иванову Ивану Ивановичу о взыскании задолженности "
        "в размере 150 000 рублей."
    )
    result = extractor.extract(text)
    assert result.court == "Замоскворецкий районный суд города Москвы"
    assert result.case_number == "2-1234/2024"
    assert result.judge == "Ёлкиной А.Б."
    assert result.claim_amount != "Не указана"
    assert result.claim_amount_value == 150000.0


def test_extract_empty_text(extractor):
    with pytest.raises(ExtractionError):
        extractor.extract("")


@pytest.mark.parametrize(
    "case_number_text,expected",
    [
        ("Дело № А40-12345/2024", "А40-12345/2024"),
        ("дело №А12-1234/2024", "А12-1234/2024"),
        ("Дело № СИП-15/2024", "СИП-15/2024"),
        ("дело № Ф05-6789/26", "Ф05-6789/26"),
        # Общая юрисдикция и Верховный Суд — номер начинается с цифр.
        ("Дело № 2-1234/2024", "2-1234/2024"),
        ("дело № 5-КГ24-15-К2", "5-КГ24-15-К2"),
    ],
)
def test_extract_various_case_number_formats(extractor, case_number_text, expected):
    result = extractor.extract(f"{case_number_text} по иску ООО Ромашка к Иванову.")
    assert result.case_number == expected


class TestResolveParties:
    """_resolve_parties изолированно от NER — не зависит от того, что именно
    распознала Natasha, только от уже готовых списков organizations/persons."""

    def test_two_organizations_picked_as_plaintiff_and_defendant(self, extractor):
        plaintiff, defendant = extractor._resolve_parties(
            organizations=["ООО Ромашка", "ООО Василёк"], persons=[]
        )
        assert plaintiff == "ООО Ромашка"
        assert defendant == "ООО Василёк"

    def test_one_organization_and_a_person_are_not_confused(self, extractor):
        plaintiff, defendant = extractor._resolve_parties(
            organizations=["ООО Ромашка"], persons=["Иванов Иван Иванович"]
        )
        assert plaintiff == "ООО Ромашка"
        assert defendant == "Иванов Иван Иванович"

    def test_no_organizations_two_persons_are_distinct(self, extractor):
        plaintiff, defendant = extractor._resolve_parties(
            organizations=[], persons=["Иванов Иван Иванович", "Петров Пётр Петрович"]
        )
        assert plaintiff == "Иванов Иван Иванович"
        assert defendant == "Петров Пётр Петрович"
        assert plaintiff != defendant

    def test_no_organizations_single_person_never_duplicated_as_defendant(self, extractor):
        # Регрессия: раньше при пустом organizations и одном найденном лице
        # plaintiff и defendant оба откатывались на persons[0] и совпадали.
        plaintiff, defendant = extractor._resolve_parties(
            organizations=[], persons=["Иванов Иван Иванович"]
        )
        assert plaintiff == "Иванов Иван Иванович"
        assert defendant is None
        assert plaintiff != defendant

    def test_no_candidates_at_all_returns_none_none(self, extractor):
        plaintiff, defendant = extractor._resolve_parties(organizations=[], persons=[])
        assert plaintiff is None
        assert defendant is None

    def test_single_candidate_logs_warning(self, extractor, caplog):
        with caplog.at_level("WARNING"):
            extractor._resolve_parties(organizations=[], persons=["Иванов Иван Иванович"])
        assert any("ответчика" in record.message for record in caplog.records)


def test_extract_end_to_end_never_duplicates_plaintiff_and_defendant_for_single_party_text(
    extractor,
):
    # End-to-end версия той же регрессии через публичный extract(), а не
    # только через _resolve_parties напрямую — проверяет, что фикс реально
    # достаёт до результата, а не только до внутреннего метода.
    text = "Иванов Иван Иванович обратился с заявлением о пересмотре дела."
    result = extractor.extract(text)
    if result.plaintiff != "Не найден" and result.defendant != "Не найден":
        assert result.plaintiff != result.defendant
