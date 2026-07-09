"""Извлечение сущностей из юридических текстов."""

from __future__ import annotations

from natasha import Doc, MorphVocab, NewsEmbedding, NewsMorphTagger, NewsNERTagger, Segmenter

from src.api.exceptions import ExtractionError
from src.extractor.patterns import LEGAL_PATTERNS

segmenter = Segmenter()
morph_vocab = MorphVocab()
emb = NewsEmbedding()
morph_tagger = NewsMorphTagger(emb)
ner_tagger = NewsNERTagger(emb)


class EntityExtractor:
    """Извлекатель именованных сущностей из русских юридических текстов.

    Natasha's NewsNERTagger распознаёт только PER, LOC и ORG — типа MONEY
    в нём нет, поэтому суммы извлекаются через regex-паттерны (LEGAL_PATTERNS),
    а не через NER.
    """

    def extract(self, text: str) -> dict:
        """Извлекает сущности из текста."""
        if not text or not text.strip():
            raise ExtractionError("Пустой текст")

        doc = Doc(text)
        doc.segment(segmenter)
        doc.tag_morph(morph_tagger)
        doc.tag_ner(ner_tagger)

        persons: list[str] = []
        organizations: list[str] = []

        for span in doc.spans:
            if span.type == "PER":
                persons.append(span.text)
            elif span.type == "ORG":
                organizations.append(span.text)

        plaintiff = organizations[0] if organizations else (persons[0] if persons else None)
        defendant = organizations[1] if len(organizations) > 1 else (persons[0] if persons else None)

        legal = self._apply_legal_rules(text)

        return {
            "plaintiff": plaintiff or "Не найден",
            "defendant": defendant or "Не найден",
            "claim_amount": legal.get("claim_amount", "Не указана"),
            "judge": legal.get("judge", "Не найден"),
            "case_number": legal.get("case_number", "Не найден"),
            "court": legal.get("court", "Не найден"),
            "meta": {
                "persons_found": persons,
                "organizations_found": organizations,
            },
        }

    def _apply_legal_rules(self, text: str) -> dict[str, str]:
        """Применяет regex-правила."""
        result = {}
        for key, pattern in LEGAL_PATTERNS.items():
            match = pattern.search(text)
            if match:
                result[key] = match.group(1).strip()
        return result


extractor = EntityExtractor()
