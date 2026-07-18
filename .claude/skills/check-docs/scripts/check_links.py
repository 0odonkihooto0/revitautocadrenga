#!/usr/bin/env python3
"""Проверка документации репозитория.

Проверяет:
1) внутренние относительные ссылки во всех *.md — целевой файл существует;
2) каждый docs/*.md упомянут в README.md и в карте CLAUDE.md;
3) нумерация файлов NN-*.md в docs/ и experiments/ — без дублей и пропусков.

Запуск из любого места: python3 .claude/skills/check-docs/scripts/check_links.py
Без внешних зависимостей. Выход: "OK" и код 0, либо список проблем и код 1.
"""

import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


def md_files(root: Path):
    for path in sorted(root.rglob("*.md")):
        if not SKIP_DIRS.intersection(path.parts):
            yield path


def check_links(root: Path, problems: list[str]) -> None:
    for md in md_files(root):
        text = md.read_text(encoding="utf-8")
        text = INLINE_CODE_RE.sub("", FENCE_RE.sub("", text))
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            rel = target.split("#", 1)[0]
            if rel and not (md.parent / rel).resolve().exists():
                problems.append(f"битая ссылка: {md.relative_to(root)} → {target}")


def check_tables(root: Path, problems: list[str]) -> None:
    readme = (root / "README.md").read_text(encoding="utf-8")
    claude_path = root / "CLAUDE.md"
    claude = claude_path.read_text(encoding="utf-8") if claude_path.exists() else ""
    for doc in sorted((root / "docs").glob("*.md")):
        if doc.name not in readme:
            problems.append(f"docs/{doc.name} не упомянут в README.md")
        if claude and doc.name not in claude:
            problems.append(f"docs/{doc.name} не упомянут в карте CLAUDE.md")


def check_numbering(root: Path, problems: list[str]) -> None:
    for folder in ("docs", "experiments"):
        d = root / folder
        if not d.exists():
            continue
        nums = []
        for f in d.glob("*.md"):
            m = re.match(r"(\d+)-", f.name)
            if m:
                nums.append(int(m.group(1)))
        for n in sorted({n for n in nums if nums.count(n) > 1}):
            problems.append(f"{folder}/: номер {n:02d} используется несколько раз")
        uniq = sorted(set(nums))
        if uniq and uniq != list(range(uniq[0], uniq[0] + len(uniq))):
            problems.append(f"{folder}/: пропуск в нумерации, заняты номера {uniq}")


def main() -> int:
    root = find_repo_root()
    problems: list[str] = []
    check_links(root, problems)
    check_tables(root, problems)
    check_numbering(root, problems)
    if problems:
        print("Проблемы документации:")
        for p in problems:
            print(f"- {p}")
        return 1
    print("OK: ссылки целы, таблицы согласованы, нумерация без пропусков.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
