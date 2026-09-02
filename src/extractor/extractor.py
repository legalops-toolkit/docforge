"""Извлечение сущностей из текста судебного решения: NER (Natasha) + regex.

Числовые/структурные поля (номер дела, суд, судья, сумма) — регексы из
patterns.py: они детерминированы и не выигрывают от статистической модели.
Стороны (истец/ответчик) — наоборот, регексом не взять надёжно, поэтому
здесь настоящий NER: Natasha находит организации (ORG) и персоны (PER),
а _resolve_parties решает, кто из кандидатов истец, а кто ответчик.

Модели Natasha грузятся лениво (functools.cached_property), а не на уровне
модуля при импорте — импорт этого файла не должен стоить секунд загрузки
эмбеддингов, если извлечение в конкретном запуске вообще не понадобится.
"""

import logging
from dataclasses import dataclass

from natasha import Doc, MorphVocab, NewsEmbedding, NewsMorphTagger, NewsNERTagger, Segmenter

try:
    from functools import cached_property
except ImportError:  # pragma: no cover - Python >=3.11 всегда имеет cached_property
    cached_property = property  # type: ignore[assignment, misc]

from src.core.exceptions import ExtractionError
from src.extractor.patterns import LEGAL_PATTERNS

logger = logging.getLogger(__name__)

NOT_FOUND = "Не найден"
AMOUNT_NOT_FOUND = "Не указана"


@dataclass
class ExtractionResult:
    """Результат извлечения. Поля, которые не удалось найти, не остаются
    пустыми/None — им явно присваивается человекочитаемый плейсхолдер, чтобы
    клиент API видел разницу между «извлекли пустую строку» и «не нашли»."""

    court: str = NOT_FOUND
    judge: str = NOT_FOUND
    case_number: str = NOT_FOUND
    plaintiff: str = NOT_FOUND
    defendant: str = NOT_FOUND
    claim_amount: str = AMOUNT_NOT_FOUND


class EntityExtractor:
    """Извлекает суд, судью, номер дела, стороны и сумму из текста решения."""

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

    @cached_property
    def _morph_vocab(self) -> MorphVocab:
        return MorphVocab()

    def extract(self, text: str) -> ExtractionResult:
        if not text or not text.strip():
            raise ExtractionError("Пустой текст нельзя обработать: извлекать нечего.")

        organizations, persons = self._extract_named_entities(text)
        plaintiff, defendant = self._resolve_parties(organizations, persons)

        return ExtractionResult(
            court=self._match_pattern("court", text) or NOT_FOUND,
            judge=self._match_pattern("judge", text) or NOT_FOUND,
            case_number=self._match_pattern("case_number", text) or NOT_FOUND,
            plaintiff=plaintiff or NOT_FOUND,
            defendant=defendant or NOT_FOUND,
            claim_amount=self._match_pattern("claim_amount", text) or AMOUNT_NOT_FOUND,
        )

    def _match_pattern(self, key: str, text: str) -> str | None:
        match = LEGAL_PATTERNS[key].search(text)
        return match.group(1).strip() if match else None

    def _extract_named_entities(self, text: str) -> tuple[list[str], list[str]]:
        """Прогоняет NER-пайплайн Natasha и делит найденные спаны по типу.

        span.type у Natasha может быть 'ORG', 'PER' или 'LOC' — нас
        интересуют только первые два (LOC — география, не сторона дела).
        Порядок в списках — порядок появления в тексте: он важен для
        _resolve_parties (первый кандидат считается истцом).
        """
        doc = Doc(text)
        doc.segment(self._segmenter)
        doc.tag_morph(self._morph_tagger)
        doc.tag_ner(self._ner_tagger)
        for span in doc.spans:
            span.normalize(self._morph_vocab)

        organizations = [span.normal or span.text for span in doc.spans if span.type == "ORG"]
        persons = [span.normal or span.text for span in doc.spans if span.type == "PER"]
        return organizations, persons

    def _resolve_parties(
        self, organizations: list[str], persons: list[str]
    ) -> tuple[str | None, str | None]:
        """Определяет истца/ответчика из найденных кандидатов.

        Организации приоритетнее персон (истец/ответчик в юрлице чаще
        именно организация), но кандидаты всех типов — единый пул: если
        органов нет, используются персоны; если есть и то и другое —
        органы идут первыми. Если кандидат всего один — ответчик не
        дублирует истца, а остаётся None с явным предупреждением в лог.
        """
        candidates = [*organizations, *persons]

        plaintiff = candidates[0] if candidates else None
        defendant = candidates[1] if len(candidates) >= 2 else None

        if len(candidates) == 1:
            logger.warning(
                "Не удалось определить ответчика: найден только один участник дела (%s)",
                candidates[0],
            )

        return plaintiff, defendant


# Синглтон по умолчанию — переиспользуется между запросами (в т.ч. модели
# Natasha грузятся один раз на процесс, а не на каждый запрос).
extractor = EntityExtractor()
