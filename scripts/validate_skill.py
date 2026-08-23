#!/usr/bin/env python3
"""Offline validation for the ecnu-api Agent Skill repository."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
LIVE_ARTIFACT_DIR = ".live-artifacts"
MAX_TEXT_SCAN_BYTES = 4 * 1024 * 1024

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
    "tests/test_repository_contracts.py",
]

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SECRET_RE = re.compile(
    r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{16,}(?![A-Za-z0-9_-])"
)
DIMENSION_ASSIGNMENT_RE = re.compile(r"\bdimensions\s*=\s*1024\b")
AUTH_BEARER_RE = re.compile(
    r"(?i)\bauthorization\b[\"']?\s*:\s*(?:[frbu]{0,2}[\"'])?"
    r"bearer\s+([^\s\"'`]+)"
)
UNIX_USER_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_])/(?:Users|home)/([^/\s`\"'<>]+)"
)
ROOT_USER_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/root(?:/|$)")
WINDOWS_USER_PATH_RE = re.compile(
    r"(?i)\b[A-Z]:[\\/]+Users[\\/]+([^\\/\s`\"'<>]+)"
)
CURRENT_STATE_RE = re.compile(r"(?im)^#{1,6}\s+current state\s*$")
RAW_REPORT_RE = re.compile(
    r"(?i)^(?:smoke|live|raw)[-_]?(?:results?|responses?|reports?|evidence)"
    r".*\.jsonl?$"
)
PROFILE_REPORT_RE = re.compile(
    r"(?i)^(?:auth|core|compatibility|billable|all)(?:[-_].*)?\.jsonl?$"
)
MEDIA_SUFFIXES = {
    ".aac", ".flac", ".gif", ".jpeg", ".jpg", ".mp3", ".mp4",
    ".opus", ".pcm", ".png", ".wav", ".webp",
}
ALLOWED_DEVIATION_STATUSES = {
    "active", "resolved", "inconclusive", "not-retested",
}
DEVIATION_FIELD_ALIASES = {
    "tested at": "tested_at",
    "test date": "tested_at",
    "date": "tested_at",
    "environment": "environment",
    "test environment": "environment",
    "protocol and endpoint": "protocol_endpoint",
    "protocol endpoint": "protocol_endpoint",
    "protocol": "protocol",
    "endpoint": "endpoint",
    "documented expectation": "documented_expectation",
    "observed behavior": "observed_behavior",
    "actual behavior": "observed_behavior",
    "reproduction conditions": "reproduction_conditions",
    "reproduction": "reproduction_conditions",
    "impact": "impact",
    "recommended fallback": "fallback",
    "application fallback": "fallback",
    "fallback": "fallback",
    "status": "status",
}
REQUIRED_DEVIATION_FIELDS = {
    "tested_at", "environment", "documented_expectation", "observed_behavior",
    "reproduction_conditions", "impact", "fallback", "status",
}


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
            fields[key.strip()] = " ".join(part for part in continuation if part)
            continue
        fields[key.strip()] = value.strip("\"'")
        index += 1
    return fields, body


def iter_repository_files(root: Path = ROOT) -> list[Path]:
    excluded = {".git", ".venv", "__pycache__", LIVE_ARTIFACT_DIR}
    return [
        path for path in root.rglob("*")
        if path.is_file() and not any(part in excluded for part in path.parts)
    ]


def iter_text_files(root: Path = ROOT) -> list[Path]:
    text_files: list[Path] = []
    for path in iter_repository_files(root):
        with path.open("rb") as handle:
            prefix = handle.read(8192)
        if b"\x00" not in prefix:
            text_files.append(path)
    return text_files


def read_bounded_text(path: Path) -> tuple[str, bool]:
    with path.open("rb") as handle:
        data = handle.read(MAX_TEXT_SCAN_BYTES + 1)
    exceeded = len(data) > MAX_TEXT_SCAN_BYTES
    return data[:MAX_TEXT_SCAN_BYTES].decode("utf-8", errors="replace"), exceeded


def _is_placeholder(value: str) -> bool:
    value = value.strip().rstrip(",;)").lower()
    if value.startswith(("<", "$", "{", "[", "%")):
        return True
    markers = (
        "api_key", "api-key", "dummy", "example", "fake", "invalid",
        "placeholder", "redacted", "test-", "token-here", "your-",
    )
    return any(marker in value for marker in markers)


def find_literal_bearers(text: str) -> list[int]:
    violations: list[int] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in AUTH_BEARER_RE.finditer(line):
            if not _is_placeholder(match.group(1)):
                violations.append(line_number)
    return violations


def find_personal_paths(text: str) -> list[int]:
    violations: list[int] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        unix = UNIX_USER_PATH_RE.search(line)
        windows = WINDOWS_USER_PATH_RE.search(line)
        if ROOT_USER_PATH_RE.search(line):
            violations.append(line_number)
        elif unix and not _is_placeholder(unix.group(1)):
            violations.append(line_number)
        elif windows and not _is_placeholder(windows.group(1)):
            violations.append(line_number)
    return violations


def is_forbidden_artifact(relative: Path) -> bool:
    if LIVE_ARTIFACT_DIR in relative.parts:
        return False
    name = relative.name.lower()
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return True
    if relative.suffix.lower() in MEDIA_SUFFIXES:
        return True
    raw_directories = {
        "live-results", "raw-responses", "raw-results", "smoke-results",
    }
    if any(part.lower() in raw_directories for part in relative.parts[:-1]):
        return True
    return bool(RAW_REPORT_RE.fullmatch(name) or PROFILE_REPORT_RE.fullmatch(name))


def validate_agents_text(text: str) -> list[str]:
    errors: list[str] = []
    if len(text.rstrip("\n").splitlines()) > 50:
        errors.append("AGENTS.md exceeds the target maximum of 50 lines")
    if CURRENT_STATE_RE.search(text):
        errors.append("AGENTS.md must not contain a dated Current State section")
    if find_personal_paths(text):
        errors.append("AGENTS.md contains a machine-specific personal path")
    return errors


def _normalize_label(label: str) -> str:
    label = re.sub(r"[`*_]", "", label).strip().lower().replace("&", " and ")
    label = re.sub(r"[/_-]+", " ", label)
    return re.sub(r"\s+", " ", label)


def _deviation_entries(text: str) -> list[tuple[str, dict[str, str]]]:
    headings = list(re.finditer(r"(?m)^#{2,3}\s+(.+?)\s*$", text))
    entries: list[tuple[str, dict[str, str]]] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        fields: dict[str, str] = {}
        for line in text[heading.end() : end].splitlines():
            match = re.match(r"^\s*[-*]\s+(.+?)\s*:\s*(.*?)\s*$", line)
            if not match:
                continue
            alias = DEVIATION_FIELD_ALIASES.get(_normalize_label(match.group(1)))
            if alias:
                fields[alias] = match.group(2).strip(" *`")
        if fields:
            entries.append((heading.group(1).strip(), fields))
    return entries


def validate_known_deviations_text(text: str) -> list[str]:
    entries = _deviation_entries(text)
    if not entries:
        return ["known_deviations.md has no field-based deviation entries"]

    errors: list[str] = []
    for title, fields in entries:
        missing = REQUIRED_DEVIATION_FIELDS - fields.keys()
        if "protocol_endpoint" not in fields and not {"protocol", "endpoint"} <= fields.keys():
            missing.add("protocol_endpoint")
        empty = {name for name, value in fields.items() if not value}
        if missing or empty:
            labels = ", ".join(sorted(missing | empty))
            errors.append(f"deviation {title!r} is missing fields: {labels}")
        status = fields.get("status", "").lower()
        if status and status not in ALLOWED_DEVIATION_STATUSES:
            errors.append(f"deviation {title!r} has invalid status: {status}")
    return errors


def validate_gitignore_text(text: str) -> list[str]:
    rules = {
        line.strip() for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if LIVE_ARTIFACT_DIR + "/" not in rules:
        return [f".gitignore must ignore {LIVE_ARTIFACT_DIR}/"]
    return []


def collect_errors(root: Path = ROOT) -> list[str]:
    errors = [
        f"missing required file: {relative}"
        for relative in REQUIRED_FILES if not (root / relative).is_file()
    ]
    skill = root / "SKILL.md"
    if not skill.is_file():
        return errors

    text = skill.read_text(encoding="utf-8")
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
    elif root.name != name and not root.name.startswith(name):
        errors.append(f"skill directory {root.name!r} does not match name {name!r}")
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
        if file_target and not (root / file_target).exists():
            errors.append(f"broken SKILL.md link: {target}")

    for path in iter_text_files(root):
        content, exceeded = read_bounded_text(path)
        relative = path.relative_to(root)
        if exceeded:
            errors.append(
                f"text file exceeds the {MAX_TEXT_SCAN_BYTES}-byte security scan limit: {relative}"
            )
            continue
        if SECRET_RE.search(content):
            errors.append(f"possible committed API key in {relative}")
        if DIMENSION_ASSIGNMENT_RE.search(content):
            errors.append(f"undocumented LangChain dimension request in {relative}")
        for line in find_literal_bearers(content):
            errors.append(f"literal Authorization bearer value in {relative}:{line}")
        if relative != Path("AGENTS.md"):
            for line in find_personal_paths(content):
                errors.append(f"machine-specific personal path in {relative}:{line}")

    for path in iter_repository_files(root):
        relative = path.relative_to(root)
        if is_forbidden_artifact(relative):
            errors.append(
                f"generated or sensitive artifact outside {LIVE_ARTIFACT_DIR}/: {relative}"
            )
    agents = root / "AGENTS.md"
    if agents.is_file():
        errors.extend(validate_agents_text(agents.read_text(encoding="utf-8")))
    deviations = root / "references/known_deviations.md"
    if deviations.is_file():
        errors.extend(
            validate_known_deviations_text(deviations.read_text(encoding="utf-8"))
        )
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        errors.extend(validate_gitignore_text(gitignore.read_text(encoding="utf-8")))
    else:
        errors.append("missing required file: .gitignore")
    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Skill validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
