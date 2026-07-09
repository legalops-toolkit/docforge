"""Кастомные исключения API."""


class DocForgeError(Exception):
    """Базовое исключение DocForge."""


class TemplateNotFoundError(DocForgeError):
    """Шаблон не найден."""


class GenerationError(DocForgeError):
    """Ошибка генерации документа."""


class ExtractionError(DocForgeError):
    """Ошибка извлечения данных."""
