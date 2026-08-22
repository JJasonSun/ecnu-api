#!/usr/bin/env python3
"""Sanitized structural smoke tests for the ECNU API.

The default profile performs model-list checks only. POST probes that may
consume credits are opt-in. The script never prints successful model content
or the API key.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_OPENAI_BASE = "https://chat.ecnu.edu.cn/open/api/v1"
DEFAULT_ANTHROPIC_BASE = "https://chat.ecnu.edu.cn/open/api/anthropic"
KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
MAX_ERROR_TEXT = 1000


@dataclass(frozen=True)
class HttpResult:
    status: int | None
    headers: dict[str, str]
    body: bytes
    transport_error: str | None = None


def redact_text(text: str, secrets: Iterable[str] = ()) -> str:
    """Redact exact secrets and key-shaped strings."""
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED_API_KEY]")
    return KEY_PATTERN.sub("[REDACTED_API_KEY]", redacted)


def sanitize_value(value: Any, secrets: Iterable[str] = ()) -> Any:
    """Bound and redact a JSON-compatible value for a report."""
    if isinstance(value, str):
        return redact_text(value, secrets)[:MAX_ERROR_TEXT]
    if isinstance(value, list):
        return [sanitize_value(item, secrets) for item in value[:20]]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 30:
                result["..."] = "truncated"
                break
            lowered = str(key).lower()
            if lowered in {"authorization", "x-api-key", "api_key", "token"}:
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = sanitize_value(item, secrets)
        return result
    return value


def build_embedding_payload(input_value: str | list[str]) -> dict[str, Any]:
    """Build only the documented ECNU embedding request fields."""
    if isinstance(input_value, str):
        if not input_value:
            raise ValueError("embedding input must not be empty")
    elif isinstance(input_value, list):
        if not input_value or not all(
            isinstance(item, str) and item for item in input_value
        ):
            raise TypeError("embedding input must be a non-empty string array")
    else:
        raise TypeError("embedding input must be a string or string array")

    return {
        "model": "ecnu-embedding-small",
        "input": input_value,
    }


def request(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    payload: Mapping[str, Any] | None = None,
    timeout: float = 30.0,
) -> HttpResult:
    data = None
    request_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    req = Request(
        url=url,
        data=data,
        headers=request_headers,
        method=method,
    )

    try:
        with urlopen(req, timeout=timeout) as response:
            return HttpResult(
                status=response.status,
                headers={key.lower(): value for key, value in response.headers.items()},
                body=response.read(),
            )
    except HTTPError as exc:
        return HttpResult(
            status=exc.code,
            headers={key.lower(): value for key, value in exc.headers.items()},
            body=exc.read(),
        )
    except (URLError, TimeoutError, OSError) as exc:
        return HttpResult(
            status=None,
            headers={},
            body=b"",
            transport_error=f"{type(exc).__name__}: {exc}",
        )


def parse_json(body: bytes) -> Any | None:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def summarize_response(
    name: str,
    result: HttpResult,
    *,
    secrets: Iterable[str] = (),
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "status": result.status,
        "content_type": result.headers.get("content-type", ""),
        "body_bytes": len(result.body),
    }

    if result.transport_error:
        summary["transport_error"] = redact_text(
            result.transport_error,
            secrets,
        )[:MAX_ERROR_TEXT]
        return summary

    payload = parse_json(result.body)

    if name.startswith("models_") and isinstance(payload, dict):
        data = payload.get("data")
        summary["object"] = payload.get("object")
        summary["model_ids"] = [
            item.get("id")
            for item in data or []
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ][:100]

    elif name.startswith("chat_") and isinstance(payload, dict):
        summary["has_choices"] = bool(payload.get("choices"))
        summary["model"] = payload.get("model")
        usage = payload.get("usage")
        summary["usage_keys"] = sorted(usage.keys()) if isinstance(usage, dict) else []

    elif name.startswith("embedding_") and isinstance(payload, dict):
        data = payload.get("data")
        items = data if isinstance(data, list) else []
        summary["count"] = len(items)
        summary["dimensions"] = [
            len(item.get("embedding", []))
            for item in items
            if isinstance(item, dict) and isinstance(item.get("embedding"), list)
        ]

    elif name.startswith("anthropic_") and isinstance(payload, dict):
        content = payload.get("content")
        summary["type"] = payload.get("type")
        summary["model"] = payload.get("model")
        summary["content_types"] = [
            item.get("type")
            for item in content or []
            if isinstance(item, dict)
        ]

    if result.status is None or result.status >= 400:
        if payload is not None:
            summary["error"] = sanitize_value(payload, secrets)
        else:
            text = result.body.decode("utf-8", errors="replace")
            summary["error_text"] = redact_text(text, secrets)[:MAX_ERROR_TEXT]

    return summary


def run_case(
    name: str,
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None,
    payload: Mapping[str, Any] | None,
    timeout: float,
    secret: str,
) -> dict[str, Any]:
    result = request(
        method,
        url,
        headers=headers,
        payload=payload,
        timeout=timeout,
    )
    return summarize_response(name, result, secrets=(secret,))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run sanitized structural ECNU API smoke tests."
    )
    parser.add_argument(
        "--low-cost",
        action="store_true",
        help="Add small Chat Completions and embedding POST probes.",
    )
    parser.add_argument(
        "--anthropic",
        action="store_true",
        help=(
            "Add small Anthropic probes for ecnu-max and ecnu-max[1m]; "
            "these requests may consume credits."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Per-request timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--openai-base",
        default=DEFAULT_OPENAI_BASE,
        help="OpenAI-compatible base URL.",
    )
    parser.add_argument(
        "--anthropic-base",
        default=DEFAULT_ANTHROPIC_BASE,
        help="Anthropic-compatible base URL.",
    )
    parser.add_argument(
        "--account-type",
        default="unspecified",
        help="Non-secret account label for the report, such as personal-token.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON report path; stdout is always printed.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when required enabled checks fail.",
    )
    return parser


def required_check_failed(
    name: str,
    summary: Mapping[str, Any],
    *,
    enabled_low_cost: bool,
    enabled_anthropic: bool,
) -> bool:
    status = summary.get("status")
    if name == "models_valid":
        return status != 200 or not summary.get("model_ids")
    if enabled_low_cost and name == "chat_plus":
        return status != 200 or not summary.get("has_choices")
    if enabled_low_cost and name.startswith("embedding_"):
        return status != 200 or not summary.get("dimensions")
    if enabled_anthropic and name == "anthropic_ecnu_max":
        return status != 200
    # Invalid/missing-auth behavior and the [1m] suffix are diagnostic probes.
    return False


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    api_key = os.environ.get("ECNU_API_KEY")
    if not api_key:
        print(
            "ECNU_API_KEY is required. Store it in the environment; "
            "do not pass it as a command-line argument.",
            file=sys.stderr,
        )
        return 2

    openai_base = args.openai_base.rstrip("/")
    anthropic_messages = args.anthropic_base.rstrip("/") + "/v1/messages"
    auth_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    report: dict[str, Any] = {
        "meta": {
            "tested_at_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "account_type": args.account_type,
            "openai_base": openai_base,
            "anthropic_base": args.anthropic_base.rstrip("/"),
            "profiles": {
                "models": True,
                "low_cost": args.low_cost,
                "anthropic": args.anthropic,
            },
            "notes": [
                "Successful model output is intentionally omitted.",
                "Image generation and TTS are intentionally not automated.",
                "Statuses are observations, not permanent API contracts.",
            ],
        },
        "tests": {},
    }
    tests: dict[str, Any] = report["tests"]

    tests["models_valid"] = run_case(
        "models_valid",
        "GET",
        openai_base + "/models",
        headers={"Authorization": f"Bearer {api_key}"},
        payload=None,
        timeout=args.timeout,
        secret=api_key,
    )
    tests["models_invalid"] = run_case(
        "models_invalid",
        "GET",
        openai_base + "/models",
        headers={"Authorization": "Bearer invalid-smoke-test-token"},
        payload=None,
        timeout=args.timeout,
        secret=api_key,
    )
    tests["models_missing"] = run_case(
        "models_missing",
        "GET",
        openai_base + "/models",
        headers=None,
        payload=None,
        timeout=args.timeout,
        secret=api_key,
    )

    if args.low_cost:
        tests["chat_plus"] = run_case(
            "chat_plus",
            "POST",
            openai_base + "/chat/completions",
            headers=auth_headers,
            payload={
                "model": "ecnu-plus",
                "messages": [
                    {"role": "user", "content": "Reply with exactly: ok"}
                ],
                "max_tokens": 8,
            },
            timeout=args.timeout,
            secret=api_key,
        )
        tests["embedding_scalar"] = run_case(
            "embedding_scalar",
            "POST",
            openai_base + "/embeddings",
            headers=auth_headers,
            payload=build_embedding_payload("smoke test"),
            timeout=args.timeout,
            secret=api_key,
        )
        tests["embedding_array"] = run_case(
            "embedding_array",
            "POST",
            openai_base + "/embeddings",
            headers=auth_headers,
            payload=build_embedding_payload(["one", "two"]),
            timeout=args.timeout,
            secret=api_key,
        )

    if args.anthropic:
        anthropic_headers = {
            "Authorization": f"Bearer {api_key}",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        for model, name in (
            ("ecnu-max", "anthropic_ecnu_max"),
            ("ecnu-max[1m]", "anthropic_ecnu_max_1m"),
        ):
            tests[name] = run_case(
                name,
                "POST",
                anthropic_messages,
                headers=anthropic_headers,
                payload={
                    "model": model,
                    "max_tokens": 8,
                    "messages": [
                        {"role": "user", "content": "Reply with exactly: ok"}
                    ],
                },
                timeout=args.timeout,
                secret=api_key,
            )

    output_text = json.dumps(report, ensure_ascii=False, indent=2)
    print(output_text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_text + "\n", encoding="utf-8")

    if args.strict:
        failures = [
            name
            for name, summary in tests.items()
            if required_check_failed(
                name,
                summary,
                enabled_low_cost=args.low_cost,
                enabled_anthropic=args.anthropic,
            )
        ]
        if failures:
            print(
                "Strict checks failed: " + ", ".join(failures),
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
