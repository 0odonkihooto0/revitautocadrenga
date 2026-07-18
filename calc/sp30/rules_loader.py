"""Загрузка YAML-правил слоя 1 базы знаний (каталог rules/)."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

RULES_DIR = Path(__file__).resolve().parents[2] / "rules"


@lru_cache(maxsize=None)
def load_rule(name: str, doc: str = "sp30") -> dict[str, Any]:
    """Читает правило rules/<doc>/<name>.yaml (doc: sp30, sp73, ...).

    Каждое правило несёт поле source с точной ссылкой на документ и таблицу/пункт
    (требование .claude/rules/code.md).
    """
    path = RULES_DIR / doc / f"{name}.yaml"
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)
