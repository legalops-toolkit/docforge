"""Генератор .docx: Jinja2 (текст, StrictUndefined) -> python-docx (файл).

Шаблон — обычный текст с Jinja2-разметкой, каждая непустая строка после
рендера становится отдельным параграфом. StrictUndefined намеренно не даёт
шаблону тихо подставить пустую строку вместо непереданной переменной —
пропущенное поле в юридическом документе хуже явной ошибки на этапе
генерации (см. README/SECURITY.md).
"""

import io
import logging
from pathlib import Path
from typing import Any

from docx import Document
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound, UndefinedError

from src.core.config import settings
from src.core.exceptions import GenerationError, TemplateNotFoundError, TemplateRenderError

logger = logging.getLogger(__name__)


class DocumentGenerator:
    """Рендерит .j2-шаблон из templates_dir в готовый .docx (bytes)."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self.templates_dir = Path(templates_dir) if templates_dir is not None else settings.templates_dir
        self._env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,  # выход — plain text/docx, а не HTML
        )

    def generate(self, template_name: str, data: dict[str, Any]) -> bytes:
        safe_name = self._safe_template_name(template_name)
        rendered_text = self._render_template(safe_name, data)
        # Перехват — здесь, а не внутри _render_to_docx: этот метод может быть
        # переопределён/замокан (см. tests/test_generator.py), и вызывающая
        # сторона обязана гарантировать безопасное сообщение в любом случае.
        try:
            return self._render_to_docx(rendered_text)
        except Exception as exc:  # noqa: BLE001 — намеренно широкий улов на границе генерации
            logger.exception("Не удалось сформировать .docx")
            raise GenerationError("Не удалось сформировать документ. Повторите попытку позже.") from exc

    def _safe_template_name(self, template_name: str) -> str:
        """Нормализует имя шаблона и блокирует path traversal.

        `Path(...).name` отбрасывает любые директории (`../`, абсолютные
        пути, вложенные `sub/../../`) и оставляет только финальный компонент
        имени файла — итоговый путь физически не может выйти за пределы
        templates_dir, даже если вызывающий код когда-нибудь передаст сюда
        template_name не из захардкоженного TEMPLATE_MAP.

        Сообщение об ошибке использует исходный (не резолвленный) путь и имя
        шаблона — то, что и так прислал вызывающий код, — но никогда не
        абсолютный путь на диске сервера.
        """
        candidate_name = Path(template_name).name
        candidate_path = self.templates_dir / candidate_name if candidate_name else None

        if not candidate_name or candidate_path is None or not candidate_path.is_file():
            raise TemplateNotFoundError(f"Шаблон «{template_name}» не найден.")
        return candidate_name

    def _render_template(self, safe_name: str, data: dict[str, Any]) -> str:
        try:
            template = self._env.get_template(safe_name)
        except TemplateNotFound as exc:
            raise TemplateNotFoundError(f"Шаблон «{safe_name}» не найден.") from exc

        try:
            return template.render(**data)
        except UndefinedError as exc:
            logger.warning("Рендер шаблона %s: отсутствует переменная (%s)", safe_name, exc)
            raise TemplateRenderError(
                f"Шаблон «{safe_name}» ожидает переменную, которая не была передана."
            ) from exc

    def _render_to_docx(self, rendered_text: str) -> bytes:
        """Построчно переносит отрендеренный текст в docx-параграфы."""
        document = Document()
        for line in rendered_text.split("\n"):
            document.add_paragraph(line)
        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()


# Синглтон по умолчанию — переиспользуется через DI (src/api/dependencies.py),
# чтобы Environment/FileSystemLoader не пересоздавались на каждый запрос.
generator = DocumentGenerator()
