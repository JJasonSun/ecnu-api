#!/usr/bin/env python3
"""Offline validation for the ecnu-api Agent Skill repository."""

from __future__ import annotations

import re
import subprocess
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
    "references/models.md",
    "references/examples.md",
    "references/engineering.md",
    "references/audit.md",
    "references/troubleshooting.md",
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


def git_ignored_files(root: Path) -> set[Path]:
    """Untracked files Git ignores; they cannot be committed by accident."""
    try:
        output = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--others", "--ignored", "--exclude-standard"],
            capture_output=True, check=True, timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return set()  # not a Git checkout (e.g. an installed copy): scan everything
    return {(root / name).resolve() for name in output.decode("utf-8", "replace").split("\0") if name}


def iter_repository_files(root: Path = ROOT) -> list[Path]:
    excluded = {".git", ".venv", "__pycache__", LIVE_ARTIFACT_DIR}
    ignored = git_ignored_files(root)
    return [
        path for path in root.rglob("*")
        if path.is_file()
        and not any(part in excluded for part in path.relative_to(root).parts)
        and path.resolve() not in ignored
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


def heading_anchors(text: str) -> set[str]:
    """GitHub-style anchors for Markdown headings outside code fences."""
    anchors: set[str] = set()
    in_fence = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        elif not in_fence and (match := re.match(r"#{1,6}\s+(.+?)\s*$", line)):
            slug = re.sub(r"[^\w\- ]", "", match.group(1).lower()).replace(" ", "-")
            anchors.add(slug)
    return anchors


def broken_links(root: Path) -> list[str]:
    """Relative Markdown links whose file or heading anchor does not exist."""
    errors: list[str] = []
    for path in iter_repository_files(root):
        if path.suffix != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            if "://" in target or target.startswith("mailto:"):
                continue
            file_part, _, anchor = target.partition("#")
            target_path = (path.parent / file_part).resolve() if file_part else path
            relative = path.relative_to(root)
            if not target_path.exists():
                errors.append(f"broken link in {relative}: {target}")
            elif anchor and target_path.suffix == ".md" and anchor not in heading_anchors(
                target_path.read_text(encoding="utf-8")
            ):
                errors.append(f"broken anchor in {relative}: {target}")
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
    errors.extend(broken_links(root))

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
