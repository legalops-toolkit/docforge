"""Извлечение сущностей из юридических текстов."""

from __future__ import annotations

import logging
import re
from functools import cached_property

from natasha import Doc, NewsEmbedding, NewsMorphTagger, NewsNERTagger, Segmenter
from pydantic import BaseModel, Field

from src.core.exceptions import ExtractionError
from src.extractor.patterns import LEGAL_PATTERNS

logger = logging.getLogger(__name__)


def parse_amount(raw: str) -> float | None:
    """Переводит найденную в тексте сумму в число.

    В русских судебных актах разряды разделяются пробелом (в том числе
    неразрывным), а копейки — запятой: «1 234 567,89». Поэтому пробелы
    убираются целиком, а запятая приводится к точке.

    Возвращает None, если строка не разбирается — вызывающий код должен
    трактовать это как «суммы нет», а не как ноль: ноль в исковом заявлении
    хуже пустого поля.
    """
    normalized = re.sub(r"\s", "", raw).replace(",", ".")
    try:
        value = float(normalized)
    except ValueError:
        logger.warning("Не удалось привести сумму %r к числу", raw)
        return None

    if value <= 0:
        # /generate/* принимают claim_amount строго больше нуля, так что
        # ноль или отрицательное значение туда всё равно не передать.
        logger.warning("Сумма %r разобралась в неположительное число %s", raw, value)
        return None

    return value


class ExtractionMeta(BaseModel):
    persons_found: list[str] = Field(default_factory=list)
    organizations_found: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Типизированный результат извлечения — вместо голого dict."""

    plaintiff: str = "Не найден"
    defendant: str = "Не найден"
    claim_amount: str = "Не указана"
    # Та же сумма числом, пригодным для /generate/claim и /generate/appeal:
    # они принимают claim_amount как float > 0, а claim_amount выше — строка
    # ровно в том виде, в каком она стояла в тексте («500 000», «1 234 567,89»).
    # Без этого поля результат /extract нельзя передать в /generate без
    # ручной нормализации на стороне клиента, хотя весь сценарий продукта
    # состоит именно в связке «разобрали решение → сгенерировали документ».
    # None означает «сумма не найдена или не разобралась»; исходная строка при
    # этом всё равно остаётся в claim_amount, чтобы ничего не терялось.
    claim_amount_value: float | None = None
    judge: str = "Не найден"
    case_number: str = "Не найден"
    court: str = "Не найден"
    meta: ExtractionMeta = Field(default_factory=ExtractionMeta)


class EntityExtractor:
    """Извлекатель именованных сущностей из русских юридических текстов.

    Natasha's NewsNERTagger распознаёт только PER, LOC и ORG — типа MONEY
    в нём нет, поэтому суммы извлекаются через regex-паттерны (LEGAL_PATTERNS),
    а не через NER.

    Модели (Segmenter, NewsEmbedding, теггеры) загружаются лениво при первом
    обращении, а не при импорте модуля или создании экземпляра — раньше
    пять довольно тяжёлых объектов создавались на уровне модуля, из-за чего
    любой `import src.extractor.extractor` (в том числе в тестах, которые
    extractor вообще не трогают) тянул за собой полную загрузку NER-моделей.
    `functools.cached_property` гарантирует, что каждая модель создаётся
    максимум один раз за время жизни экземпляра.
    """

    @cached_property
    def _segmenter(self) -> Segmenter:
        return Segmenter()

    @cached_property
    def _embedding(self) -> NewsEmbedding:
        return NewsEmbedding()

    @cached_property
    def _morph_tagger(self) -> NewsMorphTagger:
        return NewsMorphTagger(self._embedding)

    @cached_property
    def _ner_tagger(self) -> NewsNERTagger:
        return NewsNERTagger(self._embedding)

    def extract(self, text: str) -> ExtractionResult:
        """Извлекает сущности из текста."""
        if not text or not text.strip():
            logger.warning("Получен пустой текст для извлечения сущностей")
            raise ExtractionError("Пустой текст")

        logger.info("Извлечение сущностей из текста длиной %d символов", len(text))

        doc = Doc(text)
        doc.segment(self._segmenter)
        doc.tag_morph(self._morph_tagger)
        doc.tag_ner(self._ner_tagger)

        persons: list[str] = []
        organizations: list[str] = []

        for span in doc.spans:
            if span.type == "PER":
                persons.append(span.text)
            elif span.type == "ORG":
                organizations.append(span.text)

        plaintiff, defendant = self._resolve_parties(organizations, persons)

        legal = self._apply_legal_rules(text)

        raw_amount = legal.get("claim_amount")

        result = ExtractionResult(
            plaintiff=plaintiff or "Не найден",
            defendant=defendant or "Не найден",
            claim_amount=raw_amount or "Не указана",
            claim_amount_value=parse_amount(raw_amount) if raw_amount else None,
            judge=legal.get("judge", "Не найден"),
            case_number=legal.get("case_number", "Не найден"),
            court=legal.get("court", "Не найден"),
            meta=ExtractionMeta(persons_found=persons, organizations_found=organizations),
        )
        logger.info(
            "Извлечение завершено: plaintiff=%s defendant=%s case_number=%s",
            result.plaintiff,
            result.defendant,
            result.case_number,
        )
        return result

    def _resolve_parties(
        self, organizations: list[str], persons: list[str]
    ) -> tuple[str | None, str | None]:
        """Определяет истца и ответчика по найденным организациям/лицам.

        Организации приоритетнее физлиц (в спорах между юрлицами это, как
        правило, и есть стороны дела). Кандидаты берутся из ОДНОГО общего
        пула organizations + persons, а не выбираются для каждой роли
        независимо — раньше при отсутствии организаций и plaintiff, и
        defendant одинаково откатывались на `persons[0]` и получали одно
        и то же имя. Если во втором пуле не осталось кандидата, ответчик
        остаётся None, а не дублирует истца.
        """
        candidates = organizations + [p for p in persons if p not in organizations]

        if not candidates:
            return None, None

        plaintiff = candidates[0]
        remaining = candidates[1:]
        defendant = remaining[0] if remaining else None

        if defendant is None:
            logger.warning(
                "Не удалось надёжно определить ответчика: найден только один "
                "кандидат (%s). defendant оставлен пустым вместо дублирования plaintiff.",
                plaintiff,
            )

        return plaintiff, defendant

    def _apply_legal_rules(self, text: str) -> dict[str, str]:
        """Применяет regex-правила."""
        result = {}
        for key, pattern in LEGAL_PATTERNS.items():
            match = pattern.search(text)
            if match:
                result[key] = match.group(1).strip()
        return result


extractor = EntityExtractor()
