"""Deterministic keyword search over the project knowledge.

No model is involved: the same question over the same files always returns the same records.
An excerpt is a line copied verbatim from the file, so a measured number is never reworded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

LAST_CONTEXT = "live/context/global/LASTCONTEXT.md"
KNOWLEDGE_DIRS = ("docs/adr", "docs/gotchas")
MAX_EXCERPTS = 3
WORD = re.compile(r"[a-z0-9_]{2,}")


@dataclass(frozen=True)
class Hit:
    """One matching record: its path relative to the data directory, title and verbatim lines."""

    path: str
    title: str
    excerpts: list[str]
    score: int


def records(data_dir: Path) -> list[Path]:
    """The searchable markdown files, in a fixed order."""
    found = [p for d in KNOWLEDGE_DIRS for p in sorted((data_dir / d).glob("*.md"))]
    last = data_dir / LAST_CONTEXT
    return found + ([last] if last.is_file() else [])


def _title(lines: list[str], fallback: str) -> str:
    return next((line[2:].strip() for line in lines if line.startswith("# ")), fallback)


def search(data_dir: Path, question: str) -> list[Hit]:
    """Records that contain any word of the question, best first, ties broken by path."""
    terms = sorted(set(WORD.findall(question.lower())))
    hits: list[Hit] = []
    for path in records(data_dir):
        lines = path.read_text(encoding="utf-8").splitlines()
        matching = [line for line in lines if any(t in line.lower() for t in terms)]
        score = sum(line.lower().count(t) for line in matching for t in terms)
        if score:
            relative = path.relative_to(data_dir).as_posix()
            excerpts = [line.strip() for line in matching if line.strip()][:MAX_EXCERPTS]
            hits.append(Hit(relative, _title(lines, relative), excerpts, score))
    return sorted(hits, key=lambda h: (-h.score, h.path))
