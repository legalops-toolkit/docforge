import pytest

from src.engine.generator import DocumentGenerator
from src.extractor.extractor import EntityExtractor


@pytest.fixture
def generator() -> DocumentGenerator:
    return DocumentGenerator()


@pytest.fixture
def extractor() -> EntityExtractor:
    return EntityExtractor()


@pytest.fixture
def sample_ruling_text() -> str:
    return (
        "Арбитражный суд города Москвы в составе судьи Петровой А.С. "
        'рассмотрел дело № А40-12345/2024 по иску ООО "Ромашка" '
        "к Иванову Ивану Ивановичу о взыскании задолженности "
        "в размере 500 000 рублей."
    )
