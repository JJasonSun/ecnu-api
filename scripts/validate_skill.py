#!/usr/bin/env python3
"""Offline validation for the ecnu-api Agent Skill repository."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"

REQUIRED_FILES = [
    "SKILL.md",
    "README.md",
    "AGENTS.md",
    "references/api_reference.md",
    "references/models.md",
    "references/examples.md",
    "references/workflows.md",
    "references/known_deviations.md",
    "scripts/smoke_test.py",
    "scripts/validate_skill.py",
    "tests/test_smoke_test.py",
]

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SECRET_RE = re.compile(r"\bsk-[A-Za-z0-9]{24,}\b")
DIMENSION_ASSIGNMENT_RE = re.compile(r"\bdimensions\s*=\s*1024\b")
WINDOWS_USER_PATH_RE = re.compile(r"[A-Za-z]:\\Users\\")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    try:
        _, raw_frontmatter, body = text.split("---\n", 2)
    except ValueError as exc:
        raise ValueError("SKILL.md frontmatter is not closed") from exc

    fields: dict[str, str] = {}
    lines = raw_frontmatter.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value in {">", "|"}:
            continuation: list[str] = []
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if candidate and not candidate.startswith((" ", "\t")):
                    break
                continuation.append(candidate.strip())
                index += 1
            fields[key] = " ".join(part for part in continuation if part)
            continue
        fields[key] = value.strip("\"'")
        index += 1
    return fields, body


def iter_text_files() -> list[Path]:
    paths: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        if path.suffix.lower() in {
            ".md",
            ".py",
            ".yml",
            ".yaml",
            ".txt",
            ".gitignore",
        } or path.name == ".gitignore":
            paths.append(path)
    return paths


def main() -> int:
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")

    if not SKILL.is_file():
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    text = SKILL.read_text(encoding="utf-8")
    try:
        fields, body = parse_frontmatter(text)
    except ValueError as exc:
        errors.append(str(exc))
        fields, body = {}, ""

    name = fields.get("name", "")
    description = fields.get("description", "")

    if not name:
        errors.append("frontmatter name is required")
    elif len(name) > 64 or not NAME_RE.fullmatch(name):
        errors.append("frontmatter name must be lowercase kebab-case and <=64 chars")
    elif ROOT.name != name:
        # Allow a checkout directory suffix in temporary or CI worktrees.
        if not ROOT.name.startswith(name):
            errors.append(
                f"skill directory {ROOT.name!r} does not match name {name!r}"
            )

    if not description:
        errors.append("frontmatter description is required")
    elif len(description) > 1024:
        errors.append("frontmatter description exceeds 1024 characters")

    if len(body.splitlines()) > 500:
        errors.append("SKILL.md body exceeds the recommended 500 lines")

    for target in LINK_RE.findall(body):
        if "://" in target or target.startswith("#"):
            continue
        file_target = target.split("#", 1)[0]
        if file_target and not (ROOT / file_target).exists():
            errors.append(f"broken SKILL.md link: {target}")

    for path in iter_text_files():
        content = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(ROOT)
        if SECRET_RE.search(content):
            errors.append(f"possible committed API key in {relative}")
        if DIMENSION_ASSIGNMENT_RE.search(content):
            errors.append(
                f"undocumented LangChain dimension request in {relative}"
            )
        if WINDOWS_USER_PATH_RE.search(content):
            errors.append(f"machine-specific Windows user path in {relative}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("Skill validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
