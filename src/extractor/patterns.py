"""Regex-паттерны для юридических текстов."""

import re
from re import Pattern

LEGAL_PATTERNS: dict[str, Pattern[str]] = {
    "case_number": re.compile(r"(?:Дело|дело)\s*№\s*([А-Я]\d{2}[-–]\d+/\d{4})"),
    "court": re.compile(r"(Арбитражный\s+суд\s+.+?)(?=\s+в\s+составе|[.,;])"),
    "claim_amount": re.compile(r"(?:в\s+размере|сумме?)\s+([\d\s]+)\s*(?:руб|рублей|₽)"),
    "judge": re.compile(r"(?:судь[яи])\s+([А-Я][а-яё]+\s+[А-Я]\.[А-Я]\.)"),
}
