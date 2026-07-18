"""Загрузка YAML-правил слоя 1 базы знаний (каталог rules/sp30/)."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

RULES_DIR = Path(__file__).resolve().parents[2] / "rules" / "sp30"


@lru_cache(maxsize=None)
def load_rule(name: str) -> dict[str, Any]:
    """Читает правило rules/sp30/<name>.yaml.

    Каждое правило несёт поле source с точной ссылкой на документ и таблицу/пункт
    (требование .claude/rules/code.md).
    """
    path = RULES_DIR / f"{name}.yaml"
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)
