#!/usr/bin/env python3
"""Проверяет, что зависимости в pyproject.toml и requirements*.txt совпадают.

pyproject.toml — источник правды для разработки (pip install -e .[dev]),
requirements.txt/requirements-dev.txt — то, что реально ставится в
рантайм-образ (Dockerfile, Render, Railway). Ничто не мешает поправить
версию в одном месте и забыть про другое — этот скрипт делает такое
расхождение ошибкой CI, а не сюрпризом в проде.

Использование: python scripts/check_deps_sync.py
Код возврата: 0 — синхронно, 1 — есть расхождения (список — в stdout).
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

_REQUIREMENT_LINE = re.compile(r"^([A-Za-z0-9_.\-]+(?:\[[A-Za-z0-9_,\-]+\])?)==([A-Za-z0-9_.\-]+)$")


def parse_requirements_file(path: Path) -> dict[str, str]:
    """Разбирает requirements*.txt в {имя_пакета: версия}.

    Пропускает пустые строки, комментарии и `-r other.txt`-инклюды (они
    сверяются отдельно на уровне того файла, куда указывают).
    Имя пакета нормализуется без extras (`uvicorn[standard]` -> `uvicorn`),
    чтобы сравнение с pyproject.toml было по существу, а не по записи.
    """
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-r "):
            continue
        match = _REQUIREMENT_LINE.match(line)
        if not match:
            print(f"⚠️  Не удалось разобрать строку в {path.name}: {raw_line!r}")
            continue
        name, version = match.groups()
        package_name = re.sub(r"\[.*\]$", "", name)
        result[package_name.lower()] = version
    return result


def parse_pyproject_dependencies(pyproject: dict, key_path: tuple[str, ...]) -> dict[str, str]:
    node = pyproject
    for key in key_path:
        node = node.get(key, {})
    entries = node if isinstance(node, list) else []
    result: dict[str, str] = {}
    for entry in entries:
        match = _REQUIREMENT_LINE.match(entry.strip())
        if not match:
            print(f"⚠️  Не удалось разобрать зависимость в pyproject.toml: {entry!r}")
            continue
        name, version = match.groups()
        package_name = re.sub(r"\[.*\]$", "", name)
        result[package_name.lower()] = version
    return result


def diff(label_a: str, deps_a: dict[str, str], label_b: str, deps_b: dict[str, str]) -> list[str]:
    problems: list[str] = []
    all_packages = sorted(set(deps_a) | set(deps_b))
    for package in all_packages:
        version_a = deps_a.get(package)
        version_b = deps_b.get(package)
        if version_a is None:
            problems.append(f"  - {package}: есть в {label_b} ({version_b}), нет в {label_a}")
        elif version_b is None:
            problems.append(f"  - {package}: есть в {label_a} ({version_a}), нет в {label_b}")
        elif version_a != version_b:
            problems.append(f"  - {package}: {label_a}={version_a}, {label_b}={version_b}")
    return problems


def main() -> int:
    pyproject_path = ROOT_DIR / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        pyproject = tomllib.load(f)

    pyproject_main = parse_pyproject_dependencies(pyproject, ("project", "dependencies"))
    pyproject_dev = parse_pyproject_dependencies(pyproject, ("project", "optional-dependencies", "dev"))

    requirements_main = parse_requirements_file(ROOT_DIR / "requirements.txt")
    requirements_dev = parse_requirements_file(ROOT_DIR / "requirements-dev.txt")

    all_problems: list[str] = []

    main_problems = diff("pyproject.toml[project.dependencies]", pyproject_main, "requirements.txt", requirements_main)
    if main_problems:
        all_problems.append("Основные зависимости расходятся:")
        all_problems.extend(main_problems)

    # requirements-dev.txt инклюдит requirements.txt через "-r requirements.txt",
    # поэтому в файле физически присутствуют только dev-специфичные пакеты —
    # сравниваем именно с dev-списком pyproject.toml.
    dev_problems = diff(
        "pyproject.toml[project.optional-dependencies.dev]", pyproject_dev, "requirements-dev.txt", requirements_dev
    )
    if dev_problems:
        all_problems.append("Dev-зависимости расходятся:")
        all_problems.extend(dev_problems)

    if all_problems:
        print("❌ pyproject.toml и requirements*.txt разошлись:\n")
        print("\n".join(all_problems))
        print("\nПоправьте версию в обоих местах и запустите скрипт заново.")
        return 1

    print("✅ pyproject.toml и requirements*.txt синхронизированы.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
