#!/usr/bin/env python3
"""Serial, sanitized, budgeted live checks for the ECNU API.

The default ``auth`` profile does not make billable POST requests. API hosts
are fixed, credentials come only from ``ECNU_API_KEY``, and POST requests are
never retried. Reports contain response structure, never generated content.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import http.client
import importlib.metadata
import ipaddress
import json
import math
import os
import platform
import re
import socket
import ssl
import struct
import sys
import tempfile
import time
import zlib
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence, Union
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

OPENAI_BASE = "https://chat.ecnu.edu.cn/open/api/v1"
ANTHROPIC_BASE = "https://chat.ecnu.edu.cn/open/api/anthropic"
ANTHROPIC_MESSAGES_URL = ANTHROPIC_BASE + "/v1/messages"
STATUS_URL = "https://chat.ecnu.edu.cn/status"
DEFAULT_MAX_CREDITS = 50.0
MAX_ERROR_TEXT = 1000
MAX_SANITIZED_ITEMS = 30
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_STREAM_BYTES = 1024 * 1024
MAX_STREAM_EVENTS = 1000
MAX_STREAM_SECONDS = 120.0
MAX_IMAGE_REDIRECTS = 3
PROFILES = ("auth", "core", "compatibility", "billable", "all")
CASE_LOCAL_401 = frozenset({"anthropic_max_1m", "error_unsupported_model"})

KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
BEARER_PATTERN = re.compile(
    r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;\"']+"
)
DATA_URL_PATTERN = re.compile(r"data:[^\s,;]+;base64,[A-Za-z0-9+/=_-]+", re.I)
BASE64_PATTERN = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/]{128,}={0,2}")
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.I)

CASE_FIELDS = (
    "case_id",
    "tested_at",
    "protocol",
    "endpoint",
    "model",
    "request_shape",
    "documented_expectation",
    "actual_http_status",
    "actual_content_type",
    "actual_response_shape",
    "important_headers",
    "sdk_or_transport",
    "result",
    "classification",
    "notes",
)

IMPORTANT_RESPONSE_HEADERS = frozenset(
    {
        "content-type",
        "content-length",
        "content-rate",
        "content-channels",
        "content-bits",
        "request-id",
        "x-request-id",
        "x-trace-id",
        "trace-id",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "retry-after",
    }
)

DOCUMENTED_MODELS = frozenset(
    {
        "ecnu-plus",
        "ecnu-max",
        "ecnu-embedding-small",
        "ecnu-rerank",
        "ecnu-image",
        "ecnu-tts",
    }
)
ALIASES = frozenset(
    {
        "ecnu-reasoner",
        "ecnu-reasoner-lite",
        "ecnu-turbo",
        "ecnu-vl",
        "InnoSpark",
        "educhat-r1",
        "educhat-general",
        "educhat-psychology",
        "ChatECNU",
        "gpt-4",
    }
)

ECHO_TOOL = {
    "type": "function",
    "function": {
        "name": "echo",
        "description": "Return the supplied value.",
        "parameters": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
    },
}

STRUCTURED_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "department": {"type": "string"},
    },
    "required": ["name", "department"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class HttpResult:
    status: int | None
    headers: dict[str, str]
    body: bytes
    transport_error: str | None = None


@dataclass(frozen=True)
class Execution:
    response: HttpResult
    transport: str
    attempts: int = 1
    shape_updates: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkipExecution:
    reason: str
    classification: str = "unverified"


class CaseUnavailable(RuntimeError):
    pass


PayloadFactory = Callable[["RunContext"], Optional[Mapping[str, Any]]]
CustomExecutor = Callable[["RunContext", "CaseSpec"], Union[Execution, SkipExecution]]


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    profiles: frozenset[str]
    protocol: str
    endpoint: str
    model: str | None
    method: str
    request_shape: Mapping[str, Any]
    documented_expectation: str
    response_kind: str
    expected_statuses: tuple[int, ...]
    estimated_credits: float = 0.0
    headers_kind: str = "valid"
    payload_factory: PayloadFactory | None = None
    custom_executor: CustomExecutor | None = None
    requires_valid_auth: bool = True
    required: bool = True
    capture_assistant_as: str | None = None
    evidence_classification: str = "observed"


@dataclass
class CreditBudget:
    limit: float
    planned: float = 0.0
    reserved: float = 0.0
    exhausted: bool = False

    def __post_init__(self) -> None:
        if not math.isfinite(self.limit) or self.limit < 0:
            raise ValueError("credit limit must be finite and non-negative")

    def reserve(self, credits: float) -> bool:
        """Reserve before sending; an ambiguous request can still consume credits."""
        if credits <= 0:
            return True
        if self.exhausted or self.reserved + credits > self.limit + 1e-9:
            self.exhausted = True
            return False
        self.reserved += credits
        return True

    def release_unattempted(self, credits: float) -> None:
        """Release a reservation only when execution proves no wire attempt occurred."""
        if credits > 0:
            self.reserved = max(0.0, self.reserved - credits)


@dataclass
class RunContext:
    api_key: str
    timeout: float
    artifact_dir: Path
    budget: CreditBudget
    state: dict[str, Any] = field(default_factory=dict)
    auth_gate_reason: str | None = None
    stop_reason: str | None = None
    estimated_consumed_credits: float = 0.0

    def image_data_url(self) -> str:
        path = self.artifact_dir / "vision-test.png"
        if not path.exists():
            path.write_bytes(make_test_png())
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return "data:image/png;base64," + encoded


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def redact_text(text: str, secrets: Iterable[str] = ()) -> str:
    """Redact credentials, encoded media, and potentially one-time URLs."""
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED_API_KEY]")
    redacted = BEARER_PATTERN.sub(r"\1[REDACTED_API_KEY]", redacted)
    redacted = KEY_PATTERN.sub("[REDACTED_API_KEY]", redacted)
    redacted = DATA_URL_PATTERN.sub("[REDACTED_BASE64_DATA]", redacted)
    redacted = BASE64_PATTERN.sub("[REDACTED_BASE64_DATA]", redacted)
    return URL_PATTERN.sub("[REDACTED_URL]", redacted)


def _content_length(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return len(value)
    try:
        return len(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        return len(str(value))


def sanitize_value(value: Any, secrets: Iterable[str] = ()) -> Any:
    """Return a bounded JSON value without auth, reasoning, URLs, or media."""
    if isinstance(value, str):
        return redact_text(value, secrets)[:MAX_ERROR_TEXT]
    if isinstance(value, bytes):
        return {"byte_count": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    if isinstance(value, list):
        return [sanitize_value(item, secrets) for item in value[:MAX_SANITIZED_ITEMS]]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_SANITIZED_ITEMS:
                result["..."] = "truncated"
                break
            text_key = str(key)
            lowered = text_key.lower().replace("-", "_")
            if lowered in {
                "authorization",
                "x_api_key",
                "api_key",
                "token",
                "access_token",
                "client_secret",
                "ticket",
            }:
                result[text_key] = "[REDACTED]"
            elif lowered == "reasoning_content":
                result["reasoning_content_present"] = item is not None
                result["reasoning_content_length"] = _content_length(item)
            elif lowered in {
                "messages",
                "input",
                "inputs",
                "prompt",
                "prompts",
                "content",
                "contents",
                "output",
                "outputs",
                "completion",
                "completions",
                "query",
                "queries",
                "document",
                "documents",
                "image_url",
                "text",
                "data",
                "request",
                "body",
                "payload",
                "argument",
                "arguments",
                "parameters",
                "source",
            }:
                result[text_key + "_present"] = item is not None
                result[text_key + "_length"] = _content_length(item)
            elif lowered in {"b64_json", "base64", "audio", "image_data"} and isinstance(item, str) and len(item) > 100:
                result[text_key + "_present"] = bool(item)
                result[text_key + "_length"] = len(item)
            elif lowered in {"url", "download_url", "one_time_url"}:
                result[text_key + "_present"] = bool(item)
            else:
                result[text_key] = sanitize_value(item, secrets)
        return result
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(str(value), secrets)[:MAX_ERROR_TEXT]


def parse_json(body: bytes) -> Any | None:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def bounded_error_sample(body: bytes, secrets: Iterable[str] = ()) -> str:
    parsed = parse_json(body)
    if parsed is None:
        sample = redact_text(body.decode("utf-8", errors="replace"), secrets)
    else:
        sample = json.dumps(
            sanitize_value(parsed, secrets), ensure_ascii=False, separators=(",", ":")
        )
    if len(sample) > MAX_ERROR_TEXT:
        return sample[: MAX_ERROR_TEXT - 14] + "...[truncated]"
    return sample


def extract_important_headers(headers: Mapping[str, str]) -> dict[str, str]:
    lowered = {str(key).lower(): str(value) for key, value in headers.items()}
    return {
        key: redact_text(lowered[key])[:MAX_ERROR_TEXT]
        for key in sorted(IMPORTANT_RESPONSE_HEADERS)
        if key in lowered
    }


def json_shape(value: Any) -> dict[str, Any]:
    """Describe JSON types and lengths without retaining scalar content."""
    if isinstance(value, dict):
        return {
            "type": "object",
            "fields": {str(key): json_shape(item) for key, item in value.items()},
        }
    if isinstance(value, list):
        unique: list[dict[str, Any]] = []
        for item in value[:3]:
            shape = json_shape(item)
            if shape not in unique:
                unique.append(shape)
        return {"type": "array", "length": len(value), "items": unique}
    if isinstance(value, str):
        return {"type": "string", "length": len(value)}
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    return {"type": type(value).__name__}


def build_embedding_payload(input_value: str | list[str]) -> dict[str, Any]:
    """Build only the two documented fields and reject token-ID input."""
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
    return {"model": "ecnu-embedding-small", "input": input_value}


def _read_bounded(stream: Any, limit: int) -> tuple[bytes, bool]:
    data = stream.read(limit + 1)
    return data[:limit], len(data) > limit


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Any,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


_API_OPENER = build_opener(_NoRedirect())


def _open_api_request(req: Request, timeout: float) -> Any:
    """Open one request without following or forwarding auth across redirects."""
    return _API_OPENER.open(req, timeout=timeout)


def request(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    payload: Mapping[str, Any] | None = None,
    timeout: float = 30.0,
) -> HttpResult:
    """Make exactly one request; there is deliberately no retry loop."""
    data = None
    request_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    req = Request(url=url, data=data, headers=request_headers, method=method)
    try:
        with _open_api_request(req, timeout) as response:
            body, exceeded = _read_bounded(response, MAX_RESPONSE_BYTES)
            return HttpResult(
                response.status,
                {key.lower(): value for key, value in response.headers.items()},
                body,
                "response byte limit exceeded" if exceeded else None,
            )
    except HTTPError as exc:
        body, exceeded = _read_bounded(exc, MAX_RESPONSE_BYTES)
        return HttpResult(
            exc.code,
            {key.lower(): value for key, value in (exc.headers or {}).items()},
            body,
            "error response byte limit exceeded" if exceeded else None,
        )
    except (URLError, TimeoutError, OSError) as exc:
        return HttpResult(None, {}, b"", type(exc).__name__)


def stream_request(
    url: str,
    *,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout: float,
) -> HttpResult:
    """Read SSE incrementally and stop immediately after the [DONE] event."""
    request_headers = dict(headers)
    request_headers.setdefault("Content-Type", "application/json")
    req = Request(
        url=url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    deadline = time.monotonic() + min(timeout, MAX_STREAM_SECONDS)
    try:
        with _open_api_request(req, min(timeout, MAX_STREAM_SECONDS)) as response:
            chunks: list[bytes] = []
            byte_count = 0
            event_count = 0
            while True:
                if time.monotonic() > deadline:
                    return HttpResult(
                        response.status,
                        {key.lower(): value for key, value in response.headers.items()},
                        b"".join(chunks),
                        "stream wall-time limit exceeded",
                    )
                line = response.readline(MAX_STREAM_BYTES + 1)
                if not line:
                    break
                byte_count += len(line)
                if byte_count > MAX_STREAM_BYTES:
                    return HttpResult(
                        response.status,
                        {key.lower(): value for key, value in response.headers.items()},
                        b"".join(chunks),
                        "stream byte limit exceeded",
                    )
                chunks.append(line)
                if line.startswith(b"data:"):
                    event_count += 1
                    if event_count > MAX_STREAM_EVENTS:
                        return HttpResult(
                            response.status,
                            {key.lower(): value for key, value in response.headers.items()},
                            b"".join(chunks),
                            "stream event limit exceeded",
                        )
                    if line[5:].strip() == b"[DONE]":
                        break
            return HttpResult(
                response.status,
                {key.lower(): value for key, value in response.headers.items()},
                b"".join(chunks),
            )
    except HTTPError as exc:
        body, exceeded = _read_bounded(exc, MAX_ERROR_TEXT)
        return HttpResult(
            exc.code,
            {key.lower(): value for key, value in (exc.headers or {}).items()},
            body,
            "stream error response byte limit exceeded" if exceeded else None,
        )
    except (URLError, TimeoutError, OSError) as exc:
        return HttpResult(None, {}, b"", type(exc).__name__)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def make_test_png(width: int = 16, height: int = 16) -> bytes:
    """Return a tiny white PNG containing a centered red square."""
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            red = width // 4 <= x < 3 * width // 4 and height // 4 <= y < 3 * height // 4
            row.extend((255, 0, 0, 255) if red else (255, 255, 255, 255))
        rows.append(bytes(row))
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + _png_chunk(b"IEND", b"")
    )


@contextmanager
def temporary_artifacts() -> Iterable[Path]:
    with tempfile.TemporaryDirectory(prefix="ecnu-api-smoke-") as directory:
        yield Path(directory)


def _image_dimensions(data: bytes) -> list[int] | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        offset = 8
        dimensions: list[int] | None = None
        pixel_layout: tuple[int, int] | None = None
        compressed = bytearray()
        while offset + 12 <= len(data):
            length = struct.unpack(">I", data[offset : offset + 4])[0]
            end = offset + 12 + length
            if length > MAX_RESPONSE_BYTES or end > len(data):
                return None
            kind = data[offset + 4 : offset + 8]
            chunk = data[offset + 8 : offset + 8 + length]
            expected_crc = struct.unpack(">I", data[offset + 8 + length : end])[0]
            if zlib.crc32(kind + chunk) & 0xFFFFFFFF != expected_crc:
                return None
            if kind == b"IHDR":
                if dimensions is not None or offset != 8 or length != 13:
                    return None
                width, height, bit_depth, color_type, compression, filtering, interlace = (
                    struct.unpack(">IIBBBBB", chunk)
                )
                valid_depths = {
                    0: {1, 2, 4, 8, 16},
                    2: {8, 16},
                    4: {8, 16},
                    6: {8, 16},
                }
                if (
                    width <= 0
                    or height <= 0
                    or compression != 0
                    or filtering != 0
                    or interlace != 0
                    or bit_depth not in valid_depths.get(color_type, set())
                ):
                    return None
                dimensions = [width, height]
                channels = {0: 1, 2: 3, 4: 2, 6: 4}[color_type]
                pixel_layout = (bit_depth, channels)
            elif kind == b"IDAT":
                if dimensions is None:
                    return None
                compressed.extend(chunk)
            elif kind == b"IEND":
                if (
                    length != 0
                    or dimensions is None
                    or pixel_layout is None
                    or not compressed
                    or end != len(data)
                ):
                    return None
                width, height = dimensions
                bit_depth, channels = pixel_layout
                row_bytes = (width * bit_depth * channels + 7) // 8
                expected_size = height * (row_bytes + 1)
                if expected_size <= 0 or expected_size > MAX_RESPONSE_BYTES:
                    return None
                try:
                    decompressor = zlib.decompressobj()
                    decoded = decompressor.decompress(
                        bytes(compressed), expected_size + 1
                    )
                except zlib.error:
                    return None
                return (
                    dimensions
                    if len(decoded) == expected_size
                    and decompressor.eof
                    and not decompressor.unused_data
                    and not decompressor.unconsumed_tail
                    and all(
                        decoded[row * (row_bytes + 1)] <= 4
                        for row in range(height)
                    )
                    else None
                )
            offset = end
        return None
    return None


def _image_mime(data: bytes) -> str | None:
    dimensions = _image_dimensions(data)
    if dimensions and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


def _public_ip(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    if (
        not parsed.is_global
        or parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_multicast
        or parsed.is_reserved
        or parsed.is_unspecified
    ):
        return False
    if isinstance(parsed, ipaddress.IPv6Address):
        embedded: list[ipaddress.IPv4Address] = []
        if parsed.ipv4_mapped:
            embedded.append(parsed.ipv4_mapped)
        if parsed.sixtofour:
            embedded.append(parsed.sixtofour)
        for prefix in (
            ipaddress.IPv6Network("64:ff9b::/96"),
            ipaddress.IPv6Network("64:ff9b:1::/48"),
        ):
            if parsed in prefix:
                embedded.append(ipaddress.IPv4Address(parsed.packed[-4:]))
        if any(not _public_ip(str(candidate)) for candidate in embedded):
            return False
    return True


def _resolve_public_https(url: str) -> tuple[Any, str] | None:
    if any(character in url for character in "\r\n\x00"):
        return None
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if parsed.username or parsed.password or port not in {None, 443}:
        return None
    if parsed.hostname.lower() == "localhost":
        return None
    try:
        addresses = socket.getaddrinfo(
            parsed.hostname, port or 443, type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        return None
    resolved = {item[4][0] for item in addresses}
    if not resolved or not all(_public_ip(address) for address in resolved):
        return None
    address = sorted(resolved, key=lambda item: (ipaddress.ip_address(item).version, item))[0]
    return parsed, address


def _pinned_https_get(parsed: Any, address: str, timeout: float) -> HttpResult:
    hostname = parsed.hostname
    if not hostname:
        return HttpResult(None, {}, b"", "image URL host validation failed")
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    try:
        target_bytes = target.encode("ascii")
        host_bytes = hostname.encode("idna")
    except UnicodeError:
        return HttpResult(None, {}, b"", "image URL encoding validation failed")
    try:
        with socket.create_connection((address, 443), timeout=timeout) as raw_socket:
            context = ssl.create_default_context()
            with context.wrap_socket(raw_socket, server_hostname=hostname) as tls_socket:
                tls_socket.settimeout(timeout)
                tls_socket.sendall(
                    b"GET "
                    + target_bytes
                    + b" HTTP/1.1\r\nHost: "
                    + host_bytes
                    + b"\r\nAccept: image/*\r\nConnection: close\r\n\r\n"
                )
                response = http.client.HTTPResponse(tls_socket, method="GET")
                response.begin()
                body, exceeded = _read_bounded(response, MAX_RESPONSE_BYTES)
                return HttpResult(
                    response.status,
                    {key.lower(): value for key, value in response.headers.items()},
                    body,
                    "image download byte limit exceeded" if exceeded else None,
                )
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        return HttpResult(None, {}, b"", type(exc).__name__)


def fetch_public_image(url: str, timeout: float) -> HttpResult:
    """Fetch one bounded image with each DNS result pinned to its TLS socket."""
    current = url
    for redirect_count in range(MAX_IMAGE_REDIRECTS + 1):
        resolved = _resolve_public_https(current)
        if resolved is None:
            return HttpResult(
                None,
                {},
                b"",
                "image URL did not resolve exclusively to public HTTPS addresses",
            )
        parsed, address = resolved
        result = _pinned_https_get(parsed, address, timeout)
        if result.status is not None and 300 <= result.status < 400:
            location = result.headers.get("location")
            if not location or redirect_count >= MAX_IMAGE_REDIRECTS:
                return HttpResult(None, {}, b"", "image redirect limit or location failure")
            current = urljoin(current, location)
            continue
        return result
    return HttpResult(None, {}, b"", "image redirect limit exceeded")


def classify_models(model_ids: Sequence[str]) -> dict[str, list[str]]:
    visible = set(model_ids)
    return {
        "documented-and-visible": sorted(visible & DOCUMENTED_MODELS),
        "documented-but-not-visible": sorted(DOCUMENTED_MODELS - visible),
        "visible-but-undocumented": sorted(visible - DOCUMENTED_MODELS - ALIASES),
        "alias": sorted(visible & ALIASES),
        "unknown": [],
    }


def _usage_keys(payload: Mapping[str, Any]) -> list[str]:
    usage = payload.get("usage")
    return sorted(str(key) for key in usage) if isinstance(usage, dict) else []


def _safe_model_label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    if value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", value):
        return "[REDACTED_BACKEND_PATH]"
    return redact_text(value)[:200]


def _numeric_counters(value: Any) -> Any:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)) and value >= 0:
        return value
    if isinstance(value, dict):
        result = {
            str(key): counter
            for key, item in list(value.items())[:MAX_SANITIZED_ITEMS]
            if (counter := _numeric_counters(item)) is not None
        }
        return result or None
    return None


def _usage_counters(payload: Mapping[str, Any]) -> dict[str, Any]:
    usage = _numeric_counters(payload.get("usage"))
    return usage if isinstance(usage, dict) else {}


def _chat_message(payload: Any) -> Mapping[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return None
    message = choices[0].get("message")
    return message if isinstance(message, dict) else None


def _text_length(value: Any) -> int:
    return len(value) if isinstance(value, str) else 0


def _summarize_chat(payload: Mapping[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices")
    message = _chat_message(payload) or {}
    content = message.get("content")
    reasoning = message.get("reasoning_content")
    calls = message.get("tool_calls")
    calls = calls if isinstance(calls, list) else []
    names: list[str | None] = []
    valid_arguments: list[bool] = []
    ping_arguments: list[bool] = []
    for call in calls:
        function = call.get("function") if isinstance(call, dict) else None
        function = function if isinstance(function, dict) else {}
        names.append(function.get("name") if isinstance(function.get("name"), str) else None)
        raw = function.get("arguments")
        try:
            arguments = json.loads(raw) if isinstance(raw, str) else None
        except json.JSONDecodeError:
            arguments = None
        valid_arguments.append(isinstance(arguments, dict))
        ping_arguments.append(isinstance(arguments, dict) and arguments.get("value") == "ping")
    return {
        "valid_json": True,
        "top_level_keys": sorted(payload.keys()),
        "choice_count": len(choices) if isinstance(choices, list) else 0,
        "model": _safe_model_label(payload.get("model")),
        "content_present": isinstance(content, str) and bool(content),
        "content_length": _text_length(content),
        "reasoning_content_present": isinstance(reasoning, str) and bool(reasoning),
        "reasoning_content_length": _text_length(reasoning),
        "tool_call_count": len(calls),
        "tool_names": names,
        "tool_arguments_json_valid": valid_arguments,
        "tool_ping_argument": ping_arguments,
        "usage_keys": _usage_keys(payload),
        "usage_counters": _usage_counters(payload),
    }


def _summarize_stream(body: bytes) -> dict[str, Any]:
    data_count = json_count = empty_count = text_count = reasoning_count = 0
    reasoning_length = 0
    usage_counters: dict[str, Any] = {}
    done = False
    for line in body.decode("utf-8", errors="replace").splitlines():
        if not line.startswith("data:"):
            continue
        data_count += 1
        data = line[5:].strip()
        if data == "[DONE]":
            done = True
            continue
        if not data:
            empty_count += 1
            continue
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        json_count += 1
        if isinstance(event, dict) and isinstance(event.get("usage"), dict):
            usage_counters = _usage_counters(event)
        choices = event.get("choices") if isinstance(event, dict) else None
        delta = choices[0].get("delta") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        if not isinstance(delta, dict):
            empty_count += 1
            continue
        content = delta.get("content")
        reasoning = delta.get("reasoning_content")
        if isinstance(content, str) and content:
            text_count += 1
        if isinstance(reasoning, str) and reasoning:
            reasoning_count += 1
            reasoning_length += len(reasoning)
        if not content and not reasoning:
            empty_count += 1
    return {
        "sse_data_event_count": data_count,
        "json_event_count": json_count,
        "text_delta_event_count": text_count,
        "empty_chunk_count": empty_count,
        "done_event_present": done,
        "reasoning_content_present": reasoning_count > 0,
        "reasoning_content_length": reasoning_length,
        "usage_keys": sorted(usage_counters),
        "usage_counters": usage_counters,
    }


def _summarize_responses(payload: Mapping[str, Any]) -> dict[str, Any]:
    output = payload.get("output")
    items = output if isinstance(output, list) else []
    text_length = 0
    reasoning_length = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        for part in content if isinstance(content, list) else []:
            if isinstance(part, dict):
                text_length += _text_length(part.get("text"))
        if item.get("type") == "reasoning":
            reasoning_length += _content_length(item)
    return {
        "valid_json": True,
        "top_level_keys": sorted(payload.keys()),
        "output_count": len(items),
        "output_types": [item.get("type") for item in items if isinstance(item, dict)],
        "output_text_present": text_length > 0,
        "output_text_length": text_length,
        "reasoning_content_present": reasoning_length > 0,
        "reasoning_content_length": reasoning_length,
        "model": _safe_model_label(payload.get("model")),
        "usage_keys": _usage_keys(payload),
        "usage_counters": _usage_counters(payload),
    }


def _responses_text(payload: Mapping[str, Any]) -> str:
    parts: list[str] = []
    output = payload.get("output")
    for item in output if isinstance(output, list) else []:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        for part in content if isinstance(content, list) else []:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
    return "".join(parts)


def _visual_behavior(text: str, compatibility: bool) -> str:
    lowered = text.lower()
    if ("red" in lowered or "红" in text) and ("square" in lowered or "方" in text):
        return "accept"
    return "strip-image" if compatibility and text else "other"


def _summarize_embedding(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    items = data if isinstance(data, list) else []
    return {
        "valid_json": True,
        "top_level_keys": sorted(payload.keys()),
        "count": len(items),
        "indexes": [item.get("index") for item in items if isinstance(item, dict)],
        "vector_lengths": [len(item.get("embedding", [])) for item in items if isinstance(item, dict) and isinstance(item.get("embedding"), list)],
        "model": _safe_model_label(payload.get("model")),
        "usage_keys": _usage_keys(payload),
        "usage_counters": _usage_counters(payload),
    }


def _summarize_rerank(payload: Mapping[str, Any]) -> dict[str, Any]:
    results = payload.get("results")
    items = results if isinstance(results, list) else []
    return {
        "valid_json": True,
        "top_level_keys": sorted(payload.keys()),
        "result_count": len(items),
        "indexes": [item.get("index") for item in items if isinstance(item, dict)],
        "score_types": [type(item.get("relevance_score")).__name__ for item in items if isinstance(item, dict)],
        "documents_present": ["document" in item for item in items if isinstance(item, dict)],
    }


def _summarize_anthropic(payload: Mapping[str, Any]) -> dict[str, Any]:
    content = payload.get("content")
    items = content if isinstance(content, list) else []
    text_length = sum(_text_length(item.get("text")) for item in items if isinstance(item, dict))
    reasoning_length = sum(_content_length(item) for item in items if isinstance(item, dict) and item.get("type") == "thinking")
    return {
        "valid_json": True,
        "top_level_keys": sorted(payload.keys()),
        "type": payload.get("type"),
        "model": _safe_model_label(payload.get("model")),
        "content_count": len(items),
        "content_types": [item.get("type") for item in items if isinstance(item, dict)],
        "text_present": text_length > 0,
        "text_length": text_length,
        "reasoning_content_present": reasoning_length > 0,
        "reasoning_content_length": reasoning_length,
        "usage_keys": _usage_keys(payload),
        "usage_counters": _usage_counters(payload),
    }


def _summarize_structured(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = _summarize_chat(payload)
    content = (_chat_message(payload) or {}).get("content")
    parsed = None
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            pass
    required = isinstance(parsed, dict) and all(isinstance(parsed.get(key), str) for key in ("name", "department"))
    extras = set(parsed) - {"name", "department"} if isinstance(parsed, dict) else set()
    result.update(
        {
            "structured_json_valid": isinstance(parsed, dict),
            "required_fields_valid": required,
            "additional_property_count": len(extras),
            "schema_valid": required and not extras,
            "semantic_match": isinstance(parsed, dict) and parsed.get("name") == "张三" and parsed.get("department") == "数据科学部",
        }
    )
    return result


def _vision_behavior(payload: Mapping[str, Any], compatibility: bool) -> str:
    content = (_chat_message(payload) or {}).get("content")
    if not isinstance(content, str):
        return "other"
    behavior = _visual_behavior(content, compatibility)
    return "ignore-image" if behavior == "other" and content else behavior


def summarize_response(kind: str, response: HttpResult, *, secrets: Iterable[str] = ()) -> dict[str, Any]:
    """Summarize successful structure or one bounded sanitized error sample."""
    if response.transport_error:
        return {"transport_error": redact_text(response.transport_error, secrets)[:MAX_ERROR_TEXT]}
    if response.status is None:
        return {}
    if kind == "tts" and response.status < 400:
        pcm_headers = {
            key: response.headers.get(key)
            for key in ("content-rate", "content-channels", "content-bits")
        }
        return {
            "byte_count": len(response.body),
            "sha256": hashlib.sha256(response.body).hexdigest(),
            "content_type": response.headers.get("content-type", "").split(";", 1)[0].lower(),
            "content_disposition_present": bool(response.headers.get("content-disposition")),
            "pcm_headers": pcm_headers,
            "pcm_headers_complete": all(pcm_headers.values()),
        }
    if kind == "stream" and response.status < 400:
        return _summarize_stream(response.body)
    payload = parse_json(response.body)
    if response.status >= 400:
        result = {
            "valid_json": payload is not None,
            "error_body_sample": bounded_error_sample(response.body, secrets),
            "detail_type": type(payload.get("detail")).__name__ if isinstance(payload, dict) and "detail" in payload else None,
            "error_top_level_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
            "error_value_type": type(payload.get("error")).__name__ if isinstance(payload, dict) and "error" in payload else None,
        }
        if kind in {"vision", "vision_compat", "responses_vision_compat", "anthropic_vision_compat"}:
            result["vision_behavior"] = "reject"
        return result
    if not isinstance(payload, dict):
        return {"valid_json": False, "body_bytes": len(response.body)}
    if kind == "models":
        data = payload.get("data")
        items = data if isinstance(data, list) else []
        ids = [item.get("id") for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)][:100]
        return {"valid_json": True, "top_level_keys": sorted(payload.keys()), "object": payload.get("object"), "model_count": len(ids), "model_ids": ids, "model_classification": classify_models(ids)}
    if kind in {"chat", "thinking", "tool", "thinking_tool"}:
        return _summarize_chat(payload)
    if kind in {"vision", "vision_compat"}:
        result = _summarize_chat(payload)
        result["vision_behavior"] = _vision_behavior(payload, kind == "vision_compat")
        return result
    if kind in {"responses", "responses_vision_compat"}:
        result = _summarize_responses(payload)
        if kind == "responses_vision_compat":
            result["vision_behavior"] = _visual_behavior(
                _responses_text(payload), True
            )
        return result
    if kind == "embedding":
        return _summarize_embedding(payload)
    if kind == "rerank":
        return _summarize_rerank(payload)
    if kind == "structured":
        return _summarize_structured(payload)
    if kind in {"anthropic", "anthropic_vision_compat"}:
        result = _summarize_anthropic(payload)
        if kind == "anthropic_vision_compat":
            content = payload.get("content")
            items = content if isinstance(content, list) else []
            text = "".join(
                item.get("text", "")
                for item in items if isinstance(item, dict)
            )
            result["vision_behavior"] = _visual_behavior(text, True)
        return result
    if kind == "image":
        data = payload.get("data")
        items = data if isinstance(data, list) else []
        first = items[0] if items and isinstance(items[0], dict) else {}
        return {"valid_json": True, "top_level_keys": sorted(payload.keys()), "data_count": len(items), "url_present": isinstance(first.get("url"), str), "b64_json_present": isinstance(first.get("b64_json"), str)}
    if kind in {"capture", "sdk"}:
        return sanitize_value(payload, secrets)
    return {"valid_json": True, "top_level_keys": sorted(payload.keys())}


def response_matches(kind: str, status: int | None, shape: Mapping[str, Any]) -> bool:
    if status is None:
        return False
    if status >= 400:
        return True
    if kind == "models":
        return bool(shape.get("valid_json")) and bool(shape.get("model_ids"))
    if kind == "chat":
        return (
            bool(shape.get("choice_count"))
            and bool(shape.get("content_present"))
            and bool(shape.get("usage_keys"))
        )
    if kind == "thinking":
        return (
            bool(shape.get("choice_count"))
            and bool(shape.get("content_present"))
            and bool(shape.get("usage_keys"))
        )
    if kind in {"vision", "vision_compat"}:
        return bool(shape.get("choice_count")) and bool(shape.get("content_present"))
    if kind == "structured":
        return bool(shape.get("choice_count")) and bool(shape.get("schema_valid"))
    if kind in {"tool", "thinking_tool"}:
        matches = (
            bool(shape.get("tool_call_count"))
            and all(name == "echo" for name in shape.get("tool_names", []))
            and all(shape.get("tool_arguments_json_valid", []))
            and all(shape.get("tool_ping_argument", []))
        )
        return matches and (
            kind != "thinking_tool" or bool(shape.get("reasoning_content_present"))
        )
    if kind == "stream":
        return bool(shape.get("done_event_present")) and bool(shape.get("text_delta_event_count"))
    if kind in {"responses", "responses_vision_compat"}:
        return (
            bool(shape.get("output_count"))
            and bool(shape.get("output_text_present"))
            and bool(shape.get("usage_keys"))
        )
    if kind == "embedding":
        lengths = shape.get("vector_lengths")
        return (
            bool(shape.get("count"))
            and isinstance(lengths, list)
            and bool(lengths)
            and all(length == 1024 for length in lengths)
        )
    if kind == "rerank":
        count = shape.get("result_count")
        indexes = shape.get("indexes")
        score_types = shape.get("score_types")
        return (
            isinstance(count, int)
            and not isinstance(count, bool)
            and count > 0
            and isinstance(indexes, list)
            and len(indexes) == count
            and all(isinstance(index, int) and not isinstance(index, bool) and index >= 0 for index in indexes)
            and len(set(indexes)) == count
            and isinstance(score_types, list)
            and len(score_types) == count
            and all(score_type in {"float", "int"} for score_type in score_types)
        )
    if kind in {"anthropic", "anthropic_vision_compat"}:
        return bool(shape.get("content_count")) and bool(shape.get("text_present"))
    if kind == "tts":
        return (
            bool(shape.get("byte_count"))
            and str(shape.get("content_type", "")).startswith("audio/")
            and bool(shape.get("content_disposition_present"))
        )
    if kind == "image":
        return (
            bool(shape.get("data_count"))
            and bool(shape.get("media_verified"))
            and str(shape.get("media_content_type", "")).startswith("image/")
            and shape.get("pixel_dimensions") == [512, 512]
            and len(str(shape.get("sha256", ""))) == 64
        )
    return True


def _official_api_endpoint(endpoint: str) -> bool:
    return endpoint.startswith(OPENAI_BASE) or endpoint.startswith(ANTHROPIC_BASE)


def _counter(counters: Mapping[str, Any], *path: str) -> float:
    value: Any = counters
    for key in path:
        if not isinstance(value, dict):
            return 0.0
        value = value.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else 0.0


def _effective_dialog_model(model: str | None) -> str:
    lowered = (model or "").lower().split("[", 1)[0]
    if lowered in {"ecnu-max", "ecnu-reasoner"} or re.search(
        r"(?:^|[-_/])opus(?:$|[-_/0-9])", lowered
    ):
        return "ecnu-max"
    return "ecnu-plus"


def _minimum_output_credit(model: str | None, payload: Mapping[str, Any] | None) -> float:
    if payload is None:
        return 0.0
    raw_limit = payload.get("max_output_tokens", payload.get("max_tokens"))
    if isinstance(raw_limit, bool) or not isinstance(raw_limit, (int, float)):
        return 0.0
    limit = max(float(raw_limit), 0.0)
    output_rate = 1200.0 if _effective_dialog_model(model) == "ecnu-max" else 400.0
    return limit * output_rate / 1_000_000


def estimate_consumed_credits(
    spec: CaseSpec, status: int | None, shape: Mapping[str, Any]
) -> tuple[float, str]:
    """Estimate credits conservatively from fixed prices or numeric usage."""
    if spec.method != "POST" or "MockTransport" in spec.protocol:
        return 0.0, "no billable ECNU POST"
    if spec.model == "ecnu-embedding-small" or spec.endpoint.endswith("/embeddings"):
        return 0.05, "official fixed embedding price per attempted call"
    if spec.endpoint.endswith("/rerank"):
        return 0.1, "official fixed rerank price per attempted call"
    if spec.endpoint.endswith("/audio/speech"):
        return 5.0, "official fixed TTS price per attempted call"
    if spec.endpoint.endswith("/images/generations"):
        if status is None or status == 200:
            return 30.0, "official image price; ambiguous attempts counted conservatively"
        return 0.0, "definite failed image response is not counted as a successful generation"

    counters = shape.get("usage_counters")
    if not isinstance(counters, dict) or not counters:
        return spec.estimated_credits, "planned conservative allowance; usage unavailable"
    input_tokens = _counter(counters, "prompt_tokens") or _counter(counters, "input_tokens")
    output_tokens = _counter(counters, "completion_tokens") or _counter(counters, "output_tokens")
    cached_subset = _counter(counters, "prompt_tokens_details", "cached_tokens") or _counter(counters, "input_tokens_details", "cached_tokens")
    separate_cache = _counter(counters, "cache_read_input_tokens")
    uncached = max(input_tokens - cached_subset, 0.0)
    model = _effective_dialog_model(spec.model)
    miss_rate, hit_rate, output_rate = (
        (300.0, 60.0, 1200.0)
        if model == "ecnu-max"
        else (100.0, 20.0, 400.0)
    )
    credits = (
        uncached * miss_rate
        + (cached_subset + separate_cache) * hit_rate
        + output_tokens * output_rate
    ) / 1_000_000
    return credits, f"official {model} miss/hit/output token formula"


def case_response_matches(
    spec: CaseSpec, status: int | None, shape: Mapping[str, Any]
) -> bool:
    """Apply the generic structure check plus small case-specific invariants."""
    if (
        spec.case_id == "embedding_empty_array"
        and status == 200
        and shape.get("count") == 0
    ):
        return True
    if status is not None and status >= 400 and _official_api_endpoint(spec.endpoint):
        if not shape.get("valid_json"):
            return False
        if spec.case_id == "tts_invalid_voice":
            keys = set(shape.get("error_top_level_keys", []))
            return {"error", "request_id", "details"} <= keys
    if not response_matches(spec.response_kind, status, shape):
        return False
    if status != 200:
        return True
    expected_embedding_counts = {
        "embedding_scalar": 1,
        "embedding_array": 2,
        "embedding_8192_chars": 1,
        "embedding_two_long_strings": 2,
        "openai_sdk_embedding": 1,
    }
    if spec.case_id in expected_embedding_counts:
        expected = expected_embedding_counts[spec.case_id]
        return shape.get("count") == expected and shape.get("indexes") == list(
            range(expected)
        )
    if spec.case_id == "langchain_embedding_wire_capture":
        return (
            shape.get("input_is_string_array") is True
            and shape.get("dimensions_present") is False
            and shape.get("vector_count") == 2
            and shape.get("vector_lengths") == [1024, 1024]
        )
    if spec.case_id == "langchain_embedding_live":
        return (
            shape.get("count") == 1
            and shape.get("dimensions_present") is False
            and shape.get("vector_lengths") == [1024]
        )
    if spec.case_id == "rerank_top_two":
        return shape.get("result_count") == 2
    if spec.case_id == "rerank_default":
        return shape.get("result_count") == 3
    if spec.case_id == "rerank_without_documents":
        return bool(shape.get("result_count")) and not any(
            shape.get("documents_present", [])
        )
    if spec.case_id == "rerank_with_documents":
        return bool(shape.get("result_count")) and all(
            shape.get("documents_present", [])
        )
    if spec.case_id == "tts_xiayu_pcm":
        return bool(shape.get("pcm_headers_complete"))
    if spec.case_id == "vision_direct_ecnu_plus":
        return shape.get("vision_behavior") == "accept"
    if spec.case_id in {
        "responses_max_vision_compatibility",
        "anthropic_max_vision_compatibility",
    }:
        return shape.get("vision_behavior") in {"accept", "strip-image", "other"}
    if spec.case_id in {"responses_max_effort_none", "anthropic_effort_none"}:
        return not bool(shape.get("reasoning_content_present"))
    if spec.case_id in {"responses_max_effort_low", "anthropic_effort_low"}:
        return bool(shape.get("reasoning_content_present"))
    expected_anthropic_models = {
        "anthropic_plus": "ecnu-plus",
        "anthropic_max": "ecnu-max",
        "anthropic_max_1m": "ecnu-max",
        "anthropic_max_1m_fallback_plain_max": "ecnu-max",
    }
    if spec.case_id in expected_anthropic_models:
        return shape.get("model") == expected_anthropic_models[spec.case_id]
    expected_anthropic_aliases = {
        "anthropic_sonnet_mapping": {
            "claude-sonnet-4-20250514",
            "ecnu-plus",
        },
        "anthropic_opus_mapping": {
            "claude-opus-4-1-20250805",
            "ecnu-max",
        },
    }
    if spec.case_id in expected_anthropic_aliases:
        return shape.get("model") in expected_anthropic_aliases[spec.case_id]
    return True


def make_case_record(
    spec: CaseSpec,
    *,
    tested_at: str,
    status: int | None,
    content_type: str,
    response_shape: Mapping[str, Any],
    headers: Mapping[str, str],
    transport: str,
    result: str,
    classification: str,
    notes: Sequence[str],
) -> dict[str, Any]:
    record = {
        "case_id": spec.case_id,
        "tested_at": tested_at,
        "protocol": spec.protocol,
        "endpoint": spec.endpoint,
        "model": spec.model,
        "request_shape": spec.request_shape,
        "documented_expectation": spec.documented_expectation,
        "actual_http_status": status,
        "actual_content_type": content_type,
        "actual_response_shape": dict(response_shape),
        "important_headers": dict(headers),
        "sdk_or_transport": transport,
        "result": result,
        "classification": classification,
        "notes": list(notes),
    }
    if tuple(record.keys()) != CASE_FIELDS:
        raise AssertionError("case evidence schema drifted")
    return record


def skipped_record(spec: CaseSpec, reason: str, classification: str = "application-policy") -> dict[str, Any]:
    return make_case_record(
        spec,
        tested_at=utc_now(),
        status=None,
        content_type="",
        response_shape={},
        headers={},
        transport="not executed",
        result="skipped",
        classification=classification,
        notes=[reason],
    )


def _headers(kind: str, api_key: str) -> dict[str, str] | None:
    if kind in {"public", "missing"}:
        return None
    if kind == "invalid":
        return {"Authorization": "Bearer invalid-smoke-test-token"}
    if kind == "anthropic":
        return {"Authorization": f"Bearer {api_key}", "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def raw_executor(context: RunContext, spec: CaseSpec) -> Execution | SkipExecution:
    try:
        payload = spec.payload_factory(context) if spec.payload_factory else None
    except CaseUnavailable as exc:
        return SkipExecution(str(exc))
    headers = _headers(spec.headers_kind, context.api_key) or {}
    if spec.response_kind == "stream" and payload is not None:
        response = stream_request(
            spec.endpoint,
            headers=headers,
            payload=payload,
            timeout=context.timeout,
        )
    else:
        response = request(
            spec.method,
            spec.endpoint,
            headers=headers,
            payload=payload,
            timeout=context.timeout,
        )
    return Execution(response, "urllib.request (single attempt)")


def _bounded_sdk_content(response: Any, transport: Any) -> tuple[bytes, bool]:
    try:
        content = response.content
    except Exception:
        try:
            content = response.read()
        except Exception:
            content = b""
    if isinstance(content, str):
        content = content.encode("utf-8", errors="replace")
    body = bytes(content)
    exceeded = bool(getattr(transport, "response_limit_exceeded", False)) or len(
        body
    ) > MAX_RESPONSE_BYTES
    return body[:MAX_RESPONSE_BYTES], exceeded


def _sdk_error(exc: Exception, transport: Any = None) -> HttpResult:
    response = getattr(exc, "response", None)
    if response is not None:
        content, exceeded = _bounded_sdk_content(response, transport)
        return HttpResult(
            getattr(response, "status_code", None),
            {
                str(key).lower(): str(value)
                for key, value in getattr(response, "headers", {}).items()
            },
            content,
            "SDK response byte limit exceeded" if exceeded else None,
        )
    return HttpResult(None, {}, b"", type(exc).__name__)


class RecordingHttpxTransport:
    """Sync wrapper used to prove SDK POST attempt counts."""

    def __init__(self, inner: Any):
        self.inner = inner
        self.attempt_count = 0
        self.json_bodies: list[Any] = []
        self.response_limit_exceeded = False

    def handle_request(self, request_obj: Any) -> Any:
        self.attempt_count += 1
        content = request_obj.read()
        try:
            self.json_bodies.append(json.loads(content))
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
            self.json_bodies.append(None)
        response = self.inner.handle_request(request_obj)
        import httpx

        owner = self
        inner_stream = response.stream

        class BoundedStream(httpx.SyncByteStream):
            def __iter__(self) -> Iterable[bytes]:
                total = 0
                for chunk in inner_stream:
                    remaining = MAX_RESPONSE_BYTES - total
                    if remaining <= 0:
                        owner.response_limit_exceeded = True
                        break
                    if len(chunk) > remaining:
                        owner.response_limit_exceeded = True
                        yield chunk[:remaining]
                        break
                    yield chunk
                    total += len(chunk)

            def close(self) -> None:
                inner_stream.close()

        response.stream = BoundedStream()
        return response

    def close(self) -> None:
        close = getattr(self.inner, "close", None)
        if close:
            close()


def _raw_sdk_response(raw: Any, transport: Any) -> HttpResult:
    content, exceeded = _bounded_sdk_content(raw, transport)
    return HttpResult(
        raw.status_code,
        {str(key).lower(): str(value) for key, value in raw.headers.items()},
        content,
        "SDK response byte limit exceeded" if exceeded else None,
    )


def openai_sdk_executor(resource: str, payload: Mapping[str, Any]) -> CustomExecutor:
    def execute(context: RunContext, spec: CaseSpec) -> Execution | SkipExecution:
        try:
            import httpx
            from openai import OpenAI
        except ImportError:
            return SkipExecution("optional openai/httpx dependency is not installed")
        transport = RecordingHttpxTransport(httpx.HTTPTransport())
        client_http = httpx.Client(transport=transport, timeout=context.timeout)
        try:
            client = OpenAI(api_key=context.api_key, base_url=OPENAI_BASE, timeout=context.timeout, max_retries=0, http_client=client_http)
            target: Any = client
            for component in resource.split("."):
                target = getattr(target, component)
            response = _raw_sdk_response(
                target.with_raw_response.create(**dict(payload)), transport
            )
        except Exception as exc:
            response = _sdk_error(exc, transport)
        finally:
            client_http.close()
        return Execution(response, f"openai {package_version('openai')} (max_retries=0)", transport.attempt_count, {"request_attempt_count": transport.attempt_count})
    return execute


def anthropic_sdk_executor(payload: Mapping[str, Any]) -> CustomExecutor:
    def execute(context: RunContext, spec: CaseSpec) -> Execution | SkipExecution:
        try:
            import httpx
            from anthropic import Anthropic
        except ImportError:
            return SkipExecution("optional anthropic/httpx dependency is not installed")
        transport = RecordingHttpxTransport(httpx.HTTPTransport())
        client_http = httpx.Client(transport=transport, timeout=context.timeout)
        try:
            client = Anthropic(api_key=context.api_key, base_url=ANTHROPIC_BASE, timeout=context.timeout, max_retries=0, http_client=client_http)
            response = _raw_sdk_response(
                client.messages.with_raw_response.create(**dict(payload)), transport
            )
        except Exception as exc:
            response = _sdk_error(exc, transport)
        finally:
            client_http.close()
        return Execution(response, f"anthropic {package_version('anthropic')} (max_retries=0)", transport.attempt_count, {"request_attempt_count": transport.attempt_count})
    return execute


def run_langchain_mock_capture() -> tuple[dict[str, Any], int]:
    """Use local MockTransport to observe the exact LangChain request body."""
    import httpx
    from langchain_openai import OpenAIEmbeddings

    def handler(request_obj: Any) -> Any:
        body = json.loads(request_obj.content)
        input_value = body.get("input")
        count = len(input_value) if isinstance(input_value, list) else 1
        return httpx.Response(200, json={"object": "list", "data": [{"object": "embedding", "index": index, "embedding": [0.0] * 1024} for index in range(count)], "model": "ecnu-embedding-small", "usage": {"prompt_tokens": 1, "total_tokens": 1}})

    transport = RecordingHttpxTransport(httpx.MockTransport(handler))
    client_http = httpx.Client(transport=transport)
    try:
        embeddings = OpenAIEmbeddings(api_key="offline-test-key", base_url=OPENAI_BASE, model="ecnu-embedding-small", check_embedding_ctx_length=False, max_retries=0, http_client=client_http)
        vectors = embeddings.embed_documents(["one", "two"])
    finally:
        client_http.close()
    body = transport.json_bodies[-1]
    return {
        "request_keys": sorted(body.keys()) if isinstance(body, dict) else [],
        "input_is_string_array": isinstance(body, dict) and isinstance(body.get("input"), list) and all(isinstance(item, str) for item in body["input"]),
        "dimensions_present": isinstance(body, dict) and "dimensions" in body,
        "vector_count": len(vectors),
        "vector_lengths": [len(vector) for vector in vectors],
    }, transport.attempt_count


def langchain_capture_executor(context: RunContext, spec: CaseSpec) -> Execution | SkipExecution:
    try:
        shape, attempts = run_langchain_mock_capture()
    except ImportError:
        return SkipExecution("optional langchain-openai/httpx dependency is not installed")
    except Exception as exc:
        return Execution(HttpResult(None, {}, b"", type(exc).__name__), "langchain-openai local mock", 0)
    response = HttpResult(200, {"content-type": "application/json"}, json.dumps(shape).encode())
    return Execution(response, f"langchain-openai {package_version('langchain-openai')} local MockTransport", attempts)


def langchain_live_executor(context: RunContext, spec: CaseSpec) -> Execution | SkipExecution:
    try:
        import httpx
        from langchain_openai import OpenAIEmbeddings
    except ImportError:
        return SkipExecution("optional langchain-openai/httpx dependency is not installed")
    transport = RecordingHttpxTransport(httpx.HTTPTransport())
    client_http = httpx.Client(transport=transport, timeout=context.timeout)
    try:
        embeddings = OpenAIEmbeddings(api_key=context.api_key, base_url=OPENAI_BASE, model="ecnu-embedding-small", check_embedding_ctx_length=False, max_retries=0, timeout=context.timeout, http_client=client_http)
        vector = embeddings.embed_query("smoke test")
        last = transport.json_bodies[-1] if transport.json_bodies else None
        body = json.dumps({"count": 1, "vector_lengths": [len(vector)], "dimensions_present": isinstance(last, dict) and "dimensions" in last}).encode()
        response = HttpResult(200, {"content-type": "application/json"}, body)
    except Exception as exc:
        response = _sdk_error(exc, transport)
    finally:
        client_http.close()
    return Execution(response, f"langchain-openai {package_version('langchain-openai')} (max_retries=0)", transport.attempt_count, {"request_attempt_count": transport.attempt_count})


def image_executor(context: RunContext, spec: CaseSpec) -> Execution | SkipExecution:
    executed = raw_executor(context, spec)
    if isinstance(executed, SkipExecution):
        return executed
    response = executed.response
    updates: dict[str, Any] = {}
    if response.status == 200:
        payload = parse_json(response.body)
        data = payload.get("data") if isinstance(payload, dict) else None
        first = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else {}
        media = None
        declared_mime = None
        b64_value = first.get("b64_json")
        url_value = first.get("url")
        if isinstance(b64_value, str):
            try:
                media = base64.b64decode(b64_value, validate=True)
                updates["media_decode_valid"] = True
                updates["media_source"] = "b64_json"
            except (ValueError, base64.binascii.Error):
                updates["media_decode_valid"] = False
        elif isinstance(url_value, str):
            updates["download_url_present"] = True
            updates["media_source"] = "url"
            downloaded = fetch_public_image(url_value, context.timeout)
            updates["download_http_status"] = downloaded.status
            declared_mime = downloaded.headers.get("content-type", "").split(";", 1)[0].lower()
            updates["download_content_type"] = declared_mime
            if downloaded.transport_error:
                updates["media_verification_inconclusive"] = True
                updates["download_error"] = downloaded.transport_error
            elif downloaded.status == 200:
                media = downloaded.body
        if media is not None:
            inferred_mime = _image_mime(media)
            dimensions = _image_dimensions(media)
            verified = bool(
                media
                and inferred_mime
                and dimensions
                and (declared_mime is None or declared_mime.startswith("image/"))
            )
            updates.update(
                {
                    "byte_count": len(media),
                    "sha256": hashlib.sha256(media).hexdigest(),
                    "media_content_type": inferred_mime,
                    "pixel_dimensions": dimensions,
                    "media_verified": verified,
                }
            )
            if not verified and not media.startswith(b"\x89PNG\r\n\x1a\n"):
                updates["media_verification_inconclusive"] = True
                updates["media_validation_scope"] = "non-interlaced PNG only"
    return Execution(response, executed.transport, executed.attempts, updates)


def _payload(value: Mapping[str, Any]) -> PayloadFactory:
    return lambda context: copy.deepcopy(value)


def _chat_payload(model: str, max_tokens: int = 16) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "user", "content": "只回复字符串 ECNU_OK，不要添加其他文字。"}
        ],
        "max_tokens": max_tokens,
    }


def _vision_payload(context: RunContext, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "说出图中的颜色和形状。"},
                    {
                        "type": "image_url",
                        "image_url": {"url": context.image_data_url()},
                    },
                ],
            }
        ],
        "max_tokens": 32,
    }


def _responses_vision_payload(context: RunContext) -> dict[str, Any]:
    return {
        "model": "ecnu-max",
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "说出图中的颜色和形状。"},
                    {"type": "input_image", "image_url": context.image_data_url()},
                ],
            }
        ],
        "max_output_tokens": 32,
    }


def _anthropic_vision_payload(context: RunContext) -> Mapping[str, Any]:
    encoded = context.image_data_url().split(",", 1)[1]
    return {
        "model": "ecnu-max",
        "max_tokens": 32,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": encoded,
                        },
                    },
                    {"type": "text", "text": "说出图中的颜色和形状。"},
                ],
            }
        ],
    }


def _thinking_tool_followup(
    context: RunContext, *, include_reasoning: bool
) -> Mapping[str, Any]:
    assistant = context.state.get("thinking_tool_assistant")
    if not isinstance(assistant, dict):
        raise CaseUnavailable("thinking-tool first turn did not yield an assistant message")
    calls = assistant.get("tool_calls")
    if not isinstance(calls, list) or not calls or not isinstance(calls[0], dict):
        raise CaseUnavailable("thinking-tool first turn did not yield a tool call")
    call_id = calls[0].get("id")
    if not isinstance(call_id, str):
        raise CaseUnavailable("thinking-tool call did not include an id")
    reasoning = assistant.get("reasoning_content")
    if include_reasoning and not (isinstance(reasoning, str) and reasoning):
        raise CaseUnavailable("thinking-tool assistant message did not include reasoning_content")
    assistant_copy = copy.deepcopy(assistant)
    if not include_reasoning:
        assistant_copy.pop("reasoning_content", None)
    return {
        "model": "ecnu-max",
        "thinking": {"type": "enabled"},
        "reasoning_effort": "low",
        "messages": [
            {
                "role": "user",
                "content": "请调用 echo 工具，value 必须是 ping，不要直接回答。",
            },
            assistant_copy,
            {"role": "tool", "tool_call_id": call_id, "content": "ping"},
        ],
        "tools": [ECHO_TOOL],
        "max_tokens": 256,
    }


def _case(
    case_id: str,
    profiles: Sequence[str],
    protocol: str,
    endpoint: str,
    model: str | None,
    payload: Mapping[str, Any] | None,
    expectation: str,
    kind: str,
    statuses: Sequence[int],
    *,
    method: str = "POST",
    cost: float = 0.0,
    headers_kind: str = "valid",
    payload_factory: PayloadFactory | None = None,
    custom_executor: CustomExecutor | None = None,
    requires_valid_auth: bool = True,
    required: bool = True,
    capture: str | None = None,
    classification: str = "observed",
) -> CaseSpec:
    output_floor = _minimum_output_credit(model, payload)
    if method == "POST" and cost + 1e-9 < output_floor:
        raise ValueError(
            f"{case_id} reserves {cost:g} credits below its {output_floor:g} output-only floor"
        )
    return CaseSpec(
        case_id=case_id,
        profiles=frozenset(profiles),
        protocol=protocol,
        endpoint=endpoint,
        model=model,
        method=method,
        request_shape=json_shape(payload) if payload is not None else {"type": "none"},
        documented_expectation=expectation,
        response_kind=kind,
        expected_statuses=tuple(statuses),
        estimated_credits=cost,
        headers_kind=headers_kind,
        payload_factory=payload_factory or (_payload(payload) if payload is not None else None),
        custom_executor=custom_executor,
        requires_valid_auth=requires_valid_auth,
        required=required,
        capture_assistant_as=capture,
        evidence_classification=classification,
    )


def _auth_cases() -> list[CaseSpec]:
    all_profiles = ("auth", "core", "compatibility", "billable")
    return [
        _case(
            "service_status",
            all_profiles,
            "HTTPS",
            STATUS_URL,
            None,
            None,
            "The public service-status page should be reachable.",
            "generic",
            (200,),
            method="GET",
            headers_kind="public",
            requires_valid_auth=False,
        ),
        _case(
            "models_valid",
            all_profiles,
            "OpenAI-compatible",
            OPENAI_BASE + "/models",
            None,
            None,
            "A valid token should return an OpenAI-style model list.",
            "models",
            (200,),
            method="GET",
        ),
        _case(
            "models_invalid_token",
            ("auth",),
            "OpenAI-compatible",
            OPENAI_BASE + "/models",
            None,
            None,
            "Invalid authentication is documented as 401.",
            "models",
            (401,),
            method="GET",
            headers_kind="invalid",
            requires_valid_auth=False,
        ),
        _case(
            "models_missing_auth",
            ("auth",),
            "OpenAI-compatible",
            OPENAI_BASE + "/models",
            None,
            None,
            "Missing authentication is documented as 401.",
            "models",
            (401,),
            method="GET",
            headers_kind="missing",
            requires_valid_auth=False,
        ),
    ]


def _chat_response_cases() -> list[CaseSpec]:
    endpoint = OPENAI_BASE + "/chat/completions"
    cases: list[CaseSpec] = []
    for model, cost in (("ecnu-plus", 0.03), ("ecnu-max", 0.06)):
        cases.append(
            _case(
                "chat_basic_" + model.replace("-", "_"),
                ("core",),
                "OpenAI-compatible",
                endpoint,
                model,
                _chat_payload(model),
                "Chat Completions returns choices[].message.content and usage.",
                "chat",
                (200,),
                cost=cost,
            )
        )
    stream = _chat_payload("ecnu-plus", 24)
    stream["stream"] = True
    cases.append(
        _case(
            "chat_stream_ecnu_plus",
            ("core",),
            "OpenAI-compatible SSE",
            endpoint,
            "ecnu-plus",
            stream,
            "Streaming emits data events, text deltas, and [DONE].",
            "stream",
            (200,),
            cost=0.04,
        )
    )
    thinking = _chat_payload("ecnu-max", 64)
    thinking.update({"thinking": {"type": "enabled"}, "reasoning_effort": "low"})
    cases.append(
        _case(
            "chat_thinking_low",
            ("core",),
            "OpenAI-compatible",
            endpoint,
            "ecnu-max",
            thinking,
            "ecnu-max accepts thinking enabled with reasoning_effort low.",
            "thinking",
            (200,),
            cost=0.15,
        )
    )
    invalid_effort = copy.deepcopy(thinking)
    invalid_effort["reasoning_effort"] = "invalid"
    cases.append(
        _case(
            "chat_invalid_reasoning_effort",
            ("core",),
            "OpenAI-compatible",
            endpoint,
            "ecnu-max",
            invalid_effort,
            "reasoning_effort accepts only low, high, or max.",
            "generic",
            (400, 422),
            cost=0.15,
        )
    )
    tool = {
        "model": "ecnu-plus",
        "messages": [{"role": "user", "content": "请调用 echo 工具，value 必须是 ping，不要直接回答。"}],
        "tools": [ECHO_TOOL],
        "max_tokens": 64,
    }
    cases.append(
        _case(
            "chat_tool_echo",
            ("core",),
            "OpenAI-compatible",
            endpoint,
            "ecnu-plus",
            tool,
            "Tool calling returns a JSON echo(value=ping) tool call.",
            "tool",
            (200,),
            cost=0.08,
        )
    )
    thinking_tool = copy.deepcopy(tool)
    thinking_tool.update({"model": "ecnu-max", "thinking": {"type": "enabled"}, "reasoning_effort": "low"})
    thinking_tool["max_tokens"] = 256
    cases.append(
        _case(
            "chat_thinking_tool_first",
            ("core",),
            "OpenAI-compatible",
            endpoint,
            "ecnu-max",
            thinking_tool,
            "Thinking plus tools returns an assistant tool call.",
            "thinking_tool",
            (200,),
            cost=0.55,
            capture="thinking_tool_assistant",
        )
    )
    followup_shape = {
        "model": "ecnu-max",
        "thinking": {"type": "enabled"},
        "reasoning_effort": "low",
        "messages": [
            {"role": "user", "content": "synthetic"},
            {"role": "assistant", "reasoning_content": "not-persisted", "tool_calls": [ECHO_TOOL]},
            {"role": "tool", "tool_call_id": "synthetic", "content": "ping"},
        ],
        "tools": [ECHO_TOOL],
        "max_tokens": 256,
    }
    cases.append(
        _case(
            "chat_thinking_tool_continue",
            ("core",),
            "OpenAI-compatible",
            endpoint,
            "ecnu-max",
            followup_shape,
            "Splice the returned assistant message, including reasoning_content, before the tool result.",
            "chat",
            (200,),
            cost=0.65,
            payload_factory=lambda context: _thinking_tool_followup(context, include_reasoning=True),
        )
    )
    cases.append(
        _case(
            "chat_thinking_tool_omit_reasoning",
            ("core",),
            "OpenAI-compatible",
            endpoint,
            "ecnu-max",
            followup_shape,
            "Omitting reasoning_content after a thinking tool call may be rejected.",
            "generic",
            (200, 400, 422),
            cost=0.65,
            payload_factory=lambda context: _thinking_tool_followup(context, include_reasoning=False),
            required=False,
        )
    )
    responses_endpoint = OPENAI_BASE + "/responses"
    response_rows = [
        ("responses_plus_basic", "ecnu-plus", {"model": "ecnu-plus", "input": "只回复 ECNU_OK。", "max_output_tokens": 16}, "Basic Responses input produces output and usage.", 0.03),
        ("responses_max_effort_none", "ecnu-max", {"model": "ecnu-max", "input": "只回复 ECNU_OK。", "reasoning": {"effort": "none"}, "max_output_tokens": 16}, "reasoning.effort none disables thinking.", 0.07),
        ("responses_max_effort_low", "ecnu-max", {"model": "ecnu-max", "input": "只回复 ECNU_OK。", "reasoning": {"effort": "low"}, "max_output_tokens": 64}, "A valid non-none reasoning effort is accepted.", 0.13),
    ]
    for case_id, model, payload, expectation, cost in response_rows:
        cases.append(_case(case_id, ("core",), "OpenAI Responses-compatible", responses_endpoint, model, payload, expectation, "responses", (200,), cost=cost))
    return cases


def _embedding_rerank_cases() -> list[CaseSpec]:
    cases: list[CaseSpec] = []
    endpoint = OPENAI_BASE + "/embeddings"
    rows: list[tuple[str, Any, str, tuple[int, ...]]] = [
        ("embedding_scalar", "one text", "A scalar string is accepted.", (200,)),
        ("embedding_array", ["first text", "second text"], "A string array returns one ordered vector per input.", (200,)),
        ("embedding_empty_array", [], "Empty-array behavior is not documented; observe validation.", (200, 400, 422)),
        ("embedding_token_ids", [123, 456], "OpenAI integer token-ID arrays are unsupported.", (400, 422)),
        ("embedding_8192_chars", "a" * 8192, "The published input limit is 8192 characters.", (200,)),
        ("embedding_8193_chars", "a" * 8193, "Input over the 8192-character limit is rejected.", (400, 422)),
        ("embedding_two_long_strings", ["a" * 5000, "b" * 5000], "Array limit scope is undocumented; observe per-item versus total behavior.", (200, 400, 422)),
    ]
    for case_id, input_value, expectation, statuses in rows:
        payload = {"model": "ecnu-embedding-small", "input": input_value}
        cases.append(_case(case_id, ("core",), "OpenAI-compatible", endpoint, "ecnu-embedding-small", payload, expectation, "embedding", statuses, cost=0.05))

    documents = ["华东师范大学位于上海。", "量子计算使用量子比特。", "校园图书馆提供学习空间。"]
    rerank_rows = [
        ("rerank_default", {"model": "ecnu-rerank", "query": "大学在哪里", "documents": documents}, (200,), "With three documents and no top_n, all three return; this does not independently prove the documented default of 5."),
        ("rerank_top_two", {"model": "ecnu-rerank", "query": "大学在哪里", "documents": documents, "top_n": 2}, (200,), "Explicit top_n=2 returns at most two results."),
        ("rerank_without_documents", {"model": "ecnu-rerank", "query": "大学在哪里", "documents": documents, "return_documents": False}, (200,), "return_documents=false omits document text."),
        ("rerank_with_documents", {"model": "ecnu-rerank", "query": "大学在哪里", "documents": documents, "return_documents": True}, (200,), "return_documents=true includes document text."),
        ("rerank_document_8193", {"model": "ecnu-rerank", "query": "a", "documents": ["a" * 8193]}, (400, 422), "Each document is limited to 8192 characters."),
        ("rerank_top_n_over_count", {"model": "ecnu-rerank", "query": "大学在哪里", "documents": documents, "top_n": 5}, (200, 400, 422), "No maximum top_n is documented; observe values above document count."),
    ]
    endpoint = OPENAI_BASE + "/rerank"
    for case_id, payload, statuses, expectation in rerank_rows:
        cases.append(_case(case_id, ("core",), "Cohere-compatible rerank", endpoint, "ecnu-rerank", payload, expectation, "rerank", statuses, cost=0.1))
    return cases


def _vision_structured_error_cases() -> list[CaseSpec]:
    cases: list[CaseSpec] = []
    endpoint = OPENAI_BASE + "/chat/completions"
    representative_vision = {
        "model": "ecnu-plus",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "synthetic"},
                    {"type": "image_url", "image_url": {"url": "data-url-omitted"}},
                ],
            }
        ],
        "max_tokens": 32,
    }
    for model, statuses in (("ecnu-plus", (200,)), ("ecnu-max", (400, 422))):
        cases.append(
            _case(
                "vision_direct_" + model.replace("-", "_"),
                ("core",),
                "OpenAI-compatible",
                endpoint,
                model,
                {**representative_vision, "model": model},
                (
                    "ecnu-plus accepts structured text and image_url data parts."
                    if model == "ecnu-plus"
                    else "ecnu-max does not support direct Chat Completions vision."
                ),
                "vision",
                statuses,
                cost=0.1 if model == "ecnu-plus" else 0.25,
                payload_factory=lambda context, selected=model: _vision_payload(context, selected),
            )
        )
    structured = {
        "model": "ecnu-plus",
        "messages": [{"role": "user", "content": "姓名张三，部门数据科学部。仅按 schema 输出。"}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "person", "schema": STRUCTURED_SCHEMA},
        },
        "max_tokens": 128,
    }
    cases.append(
        _case(
            "structured_output_ecnu_plus",
            ("core",),
            "OpenAI-compatible",
            endpoint,
            "ecnu-plus",
            structured,
            "json_schema constrains structure, not semantic correctness.",
            "structured",
            (200,),
            cost=0.15,
        )
    )
    error_rows = [
        ("error_missing_model", {"messages": [{"role": "user", "content": "test"}]}, (400, 422), "model is required.", "valid"),
        ("error_wrong_messages_type", {"model": "ecnu-plus", "messages": "wrong-type"}, (400, 422), "messages must be an array.", "valid"),
        ("error_invalid_token_post", _chat_payload("ecnu-plus"), (401,), "Invalid POST authentication is documented as 401.", "invalid"),
        ("error_unsupported_model", _chat_payload("definitely-not-an-ecnu-model"), (400, 404, 422), "Unsupported models return a bounded error.", "valid"),
        ("error_unsupported_parameter_value", {**_chat_payload("ecnu-plus"), "temperature": 2}, (400, 422), "temperature outside 0 through 1 is unsupported.", "valid"),
    ]
    for case_id, payload, statuses, expectation, headers_kind in error_rows:
        cases.append(
            _case(
                case_id,
                ("core",),
                "OpenAI-compatible",
                endpoint,
                payload.get("model"),
                payload,
                expectation,
                "generic",
                statuses,
                cost=0.02,
                headers_kind=headers_kind,
                requires_valid_auth=headers_kind == "valid",
            )
        )
    return cases


def _optional_sdk_cases() -> list[CaseSpec]:
    cases: list[CaseSpec] = []
    sdk_rows = [
        ("openai_sdk_chat", "chat.completions", _chat_payload("ecnu-plus"), "chat", 0.03),
        ("openai_sdk_responses", "responses", {"model": "ecnu-plus", "input": "只回复 ECNU_OK。", "max_output_tokens": 16}, "responses", 0.03),
        ("openai_sdk_embedding", "embeddings", build_embedding_payload("smoke test"), "embedding", 0.05),
    ]
    for case_id, resource, payload, kind, cost in sdk_rows:
        cases.append(
            _case(
                case_id,
                ("core",),
                "OpenAI Python SDK",
                OPENAI_BASE,
                payload.get("model"),
                payload,
                "The optional SDK preserves the wire contract with retries disabled.",
                kind,
                (200,),
                cost=cost,
                custom_executor=openai_sdk_executor(resource, payload),
            )
        )
    cases.extend(
        [
            _case(
                "langchain_embedding_wire_capture",
                ("core",),
                "LangChain local MockTransport",
                OPENAI_BASE + "/embeddings",
                "ecnu-embedding-small",
                build_embedding_payload(["one", "two"]),
                "check_embedding_ctx_length=false sends strings and no dimensions field.",
                "capture",
                (200,),
                custom_executor=langchain_capture_executor,
                requires_valid_auth=False,
                classification="application-policy",
            ),
            _case(
                "langchain_embedding_live",
                ("core",),
                "LangChain OpenAIEmbeddings",
                OPENAI_BASE + "/embeddings",
                "ecnu-embedding-small",
                build_embedding_payload("smoke test"),
                "The live vector has length 1024 without sending dimensions.",
                "capture",
                (200,),
                cost=0.05,
                custom_executor=langchain_live_executor,
            ),
        ]
    )
    return cases


def _compatibility_cases() -> list[CaseSpec]:
    cases: list[CaseSpec] = []
    representative = {
        "model": "ecnu-max",
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "synthetic"},
                    {"type": "input_image", "image_url": "data-url-omitted"},
                ],
            }
        ],
    }
    cases.append(
        _case(
            "responses_max_vision_compatibility",
            ("compatibility",),
            "OpenAI Responses-compatible",
            OPENAI_BASE + "/responses",
            "ecnu-max",
            representative,
            "Not documented as a stable contract; observe current ecnu-max image handling.",
            "responses_vision_compat",
            (200,),
            cost=0.25,
            payload_factory=_responses_vision_payload,
        )
    )
    rows = [
        ("anthropic_plus", "ecnu-plus", {}, (200,), "ecnu-plus is accepted directly."),
        ("anthropic_max", "ecnu-max", {}, (200,), "ecnu-max is accepted directly."),
        ("anthropic_sonnet_mapping", "claude-sonnet-4-20250514", {}, (200,), "The sonnet alias is accepted; its response label does not prove effective ecnu-plus routing."),
        ("anthropic_opus_mapping", "claude-opus-4-1-20250805", {}, (200,), "The opus alias is accepted; its response label does not prove effective ecnu-max routing."),
        ("anthropic_max_1m_fallback_plain_max", "ecnu-max", {}, (200,), "Plain ecnu-max is the explicit control and fallback for suffix-specific failures."),
        ("anthropic_max_1m", "ecnu-max[1m]", {}, (200,), "The [1m] suffix is documented compatibility metadata."),
        ("anthropic_effort_none", "ecnu-max", {"output_config": {"effort": "none"}}, (200,), "output_config.effort none disables thinking."),
        ("anthropic_effort_low", "ecnu-max", {"output_config": {"effort": "low"}}, (200,), "A valid non-none effort is accepted."),
        ("anthropic_invalid_effort", "ecnu-max", {"output_config": {"effort": "invalid"}}, (400, 422), "Unsupported effort values are rejected."),
        ("anthropic_missing_model", None, {}, (400, 422), "model is required."),
    ]
    for case_id, model, extra, statuses, expectation in rows:
        payload: dict[str, Any] = {
            "max_tokens": 32,
            "messages": [{"role": "user", "content": "只回复 ECNU_OK。"}],
        }
        if model is not None:
            payload["model"] = model
        payload.update(extra)
        cases.append(
            _case(
                case_id,
                ("compatibility",),
                "Anthropic-compatible",
                ANTHROPIC_MESSAGES_URL,
                model,
                payload,
                expectation,
                "anthropic" if 200 in statuses else "generic",
                statuses,
                cost=0.08 if _effective_dialog_model(model) == "ecnu-max" else 0.04,
                headers_kind="anthropic",
            )
        )
    anthropic_vision_shape = {
        "model": "ecnu-max",
        "max_tokens": 32,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": "omitted"},
                    }
                ],
            }
        ],
    }
    cases.append(
        _case(
            "anthropic_max_vision_compatibility",
            ("compatibility",),
            "Anthropic-compatible",
            ANTHROPIC_MESSAGES_URL,
            "ecnu-max",
            anthropic_vision_shape,
            "Not documented as a stable contract; observe current ecnu-max image handling.",
            "anthropic_vision_compat",
            (200,),
            cost=0.25,
            headers_kind="anthropic",
            payload_factory=_anthropic_vision_payload,
        )
    )
    sdk_payload = {
        "model": "ecnu-plus",
        "max_tokens": 16,
        "messages": [{"role": "user", "content": "只回复 ECNU_OK。"}],
    }
    cases.append(
        _case(
            "anthropic_sdk_plus",
            ("compatibility",),
            "Anthropic Python SDK",
            ANTHROPIC_MESSAGES_URL,
            "ecnu-plus",
            sdk_payload,
            "The optional SDK calls the compatibility root with retries disabled.",
            "anthropic",
            (200,),
            cost=0.04,
            custom_executor=anthropic_sdk_executor(sdk_payload),
        )
    )
    return cases


def _billable_cases() -> list[CaseSpec]:
    cases: list[CaseSpec] = []
    endpoint = OPENAI_BASE + "/audio/speech"
    # Required priority under the default budget: PCM, invalid voice, one image.
    rows = [
        ("tts_xiayu_pcm", "xiayu", "pcm", (200,), "PCM returns binary audio and observable format headers.", True),
        ("tts_invalid_voice", "definitely_invalid_voice", "mp3", (400,), "An invalid voice is documented as a 400 JSON client error.", True),
    ]
    for case_id, voice, response_format, statuses, expectation, required in rows:
        payload = {"model": "ecnu-tts", "input": "你好。", "voice": voice, "response_format": response_format}
        cases.append(_case(case_id, ("billable",), "OpenAI-compatible binary", endpoint, "ecnu-tts", payload, expectation, "tts" if 200 in statuses else "generic", statuses, cost=5.0, required=required))
    image_payload = {
        "model": "ecnu-image",
        "prompt": "白底蓝色圆形图标，简洁扁平，无文字",
        "size": "512x512",
        "response_format": "url",
    }
    cases.append(
        _case(
            "image_generation_documented",
            ("billable",),
            "OpenAI-compatible",
            OPENAI_BASE + "/images/generations",
            "ecnu-image",
            image_payload,
            "At most one documented 512x512 generation returns URL or base64 image data.",
            "image",
            (200,),
            cost=30.0,
            custom_executor=image_executor,
        )
    )
    optional_rows = [
        ("tts_xiayu_mp3", "xiayu", "The default campus voice returns MP3 audio."),
        ("tts_liwa_mp3", "liwa", "The second documented campus voice returns MP3 audio."),
        ("tts_extended_voice_sample", "male_warm", "One extended voice is optional and runs only with budget remaining."),
    ]
    for case_id, voice, expectation in optional_rows:
        payload = {"model": "ecnu-tts", "input": "你好。", "voice": voice, "response_format": "mp3"}
        cases.append(
            _case(
                case_id,
                ("billable",),
                "OpenAI-compatible binary",
                endpoint,
                "ecnu-tts",
                payload,
                expectation,
                "tts",
                (200,),
                cost=5.0,
                required=False,
            )
        )
    return cases


def build_cases() -> list[CaseSpec]:
    return (
        _auth_cases()
        + _chat_response_cases()
        + _embedding_rerank_cases()
        + _vision_structured_error_cases()
        + _optional_sdk_cases()
        + _compatibility_cases()
        + _billable_cases()
    )


def _default_max_credits() -> float:
    return DEFAULT_MAX_CREDITS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run serial, sanitized ECNU API validation profiles.")
    parser.add_argument("--profile", action="append", choices=PROFILES, help="Profile to run; repeat to combine (default: auth).")
    parser.add_argument("--max-credits", type=float, default=_default_max_credits(), help="Conservative planned-credit cap (default: 50).")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--output", type=Path, help="Optional sanitized JSON path.")
    parser.add_argument(
        "--case",
        dest="case_ids",
        action="append",
        help="Run only the named case within the selected profile; repeat as needed.",
    )
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--account-type", default="unspecified")
    parser.add_argument("--network-environment", default="unspecified")
    # Clean legacy compatibility: old flags map to the new non-billable profiles.
    parser.add_argument("--low-cost", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--anthropic", action="store_true", help=argparse.SUPPRESS)
    return parser


def selected_profiles(args: argparse.Namespace, parser: argparse.ArgumentParser) -> set[str]:
    selected = set(args.profile or [])
    if selected and (args.low_cost or args.anthropic):
        parser.error("do not combine --profile with legacy --low-cost/--anthropic")
    if not selected:
        selected = {"auth"}
        if args.low_cost:
            selected = {"core"}
        if args.anthropic:
            selected.add("compatibility")
    if "all" in selected:
        return {"auth", "core", "compatibility", "billable"}
    return selected


def _local_401_has_control(context: RunContext, spec: CaseSpec) -> bool:
    if spec.case_id == "anthropic_max_1m":
        successful_models = context.state.get("successful_models")
        return isinstance(successful_models, set) and "ecnu-max" in successful_models
    return bool(context.state.get("valid_auth_observed"))


def run_one(context: RunContext, spec: CaseSpec) -> dict[str, Any]:
    if context.stop_reason:
        return skipped_record(spec, context.stop_reason)
    if spec.requires_valid_auth and context.auth_gate_reason:
        return skipped_record(spec, context.auth_gate_reason, "unverified")
    if not context.budget.reserve(spec.estimated_credits):
        return skipped_record(spec, f"credit budget stop: {spec.estimated_credits:g} more credits would exceed {context.budget.limit:g}")

    executed = (spec.custom_executor or raw_executor)(context, spec)
    if isinstance(executed, SkipExecution):
        context.budget.release_unattempted(spec.estimated_credits)
        return skipped_record(spec, executed.reason, executed.classification)
    response = executed.response
    shape = summarize_response(spec.response_kind, response, secrets=(context.api_key,))
    shape.update(sanitize_value(dict(executed.shape_updates), (context.api_key,)))
    if spec.model and isinstance(shape.get("model"), str):
        shape["response_model_matches_request"] = shape["model"] == spec.model
    consumed, credit_basis = estimate_consumed_credits(spec, response.status, shape)
    if executed.attempts > 1:
        additional = spec.estimated_credits * (executed.attempts - 1)
        consumed += additional
        credit_basis += "; unexpected extra attempts charged at planned allowance"
    shape["estimated_consumed_credits"] = round(consumed, 8)
    shape["credit_estimate_basis"] = credit_basis
    context.estimated_consumed_credits += consumed
    if executed.attempts > 1:
        shape["unexpected_retry_count"] = executed.attempts - 1

    authenticated_success = (
        spec.requires_valid_auth
        and response.status is not None
        and 200 <= response.status < 300
        and (spec.case_id != "models_valid" or bool(shape.get("model_ids")))
    )
    if authenticated_success:
        context.state["valid_auth_observed"] = True
        if spec.model:
            successful_models = context.state.setdefault("successful_models", set())
            if isinstance(successful_models, set):
                successful_models.add(spec.model)
    local_401_accepted = (
        response.status == 401
        and spec.case_id in CASE_LOCAL_401
        and _local_401_has_control(context, spec)
    )

    if response.transport_error:
        result = "inconclusive"
        notes = ["ambiguous transport outcome; the POST was not retried"]
    elif shape.get("media_verification_inconclusive"):
        result = "inconclusive"
        notes = ["image generation returned, but bounded media verification was inconclusive"]
    elif response.status not in spec.expected_statuses:
        result = "mismatch"
        notes = ["observed status differs from the documented expectation"]
    elif spec.response_kind == "stream" and not response.headers.get(
        "content-type", ""
    ).startswith("text/event-stream"):
        result = "mismatch"
        notes = ["stream body was not returned with an SSE content type"]
    elif not case_response_matches(spec, response.status, shape):
        result = "mismatch"
        notes = ["status matched but required response structure did not"]
    elif executed.attempts > 1:
        result = "mismatch"
        notes = ["transport attempted the POST more than once"]
    else:
        result = "pass"
        notes = ["structural check passed; generated content was omitted"]

    if local_401_accepted:
        notes.append("case-specific 401 does not invalidate the already verified bearer token")

    if spec.capture_assistant_as and response.status == 200:
        message = _chat_message(parse_json(response.body))
        if message:
            context.state[spec.capture_assistant_as] = copy.deepcopy(dict(message))

    if executed.attempts > 1:
        context.stop_reason = "conservative global stop after a transport attempted more than once"
    elif response.status == 429 and _official_api_endpoint(spec.endpoint):
        context.stop_reason = "conservative global stop after ECNU API HTTP 429"
    elif spec.case_id == "models_valid" and (response.status != 200 or not shape.get("model_ids")):
        context.auth_gate_reason = "valid-token model discovery did not prove authentication; authenticated POSTs stopped"
    elif spec.requires_valid_auth:
        if response.status in {401, 403} and not local_401_accepted:
            context.stop_reason = f"conservative stop after authenticated HTTP {response.status}"
        elif response.transport_error and spec.method == "POST":
            context.stop_reason = "conservative stop after an ambiguous authenticated POST"

    return make_case_record(
        spec,
        tested_at=utc_now(),
        status=response.status,
        content_type=response.headers.get("content-type", ""),
        response_shape=shape,
        headers=extract_important_headers(response.headers),
        transport=executed.transport,
        result=result,
        classification=spec.evidence_classification,
        notes=notes,
    )


def strict_failure_ids(
    records: Sequence[Mapping[str, Any]],
    specs: Mapping[str, CaseSpec],
    explicit_case_ids: set[str],
) -> list[str]:
    return [
        str(record["case_id"])
        for record in records
        if record["result"] in {"mismatch", "inconclusive"}
        or (
            record["result"] == "skipped"
            and (
                specs[str(record["case_id"])].required
                or str(record["case_id"]) in explicit_case_ids
            )
        )
    ]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not math.isfinite(args.max_credits) or args.max_credits < 0:
        parser.error("--max-credits must be finite and non-negative")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be finite and positive")
    profiles = selected_profiles(args, parser)
    api_key = os.environ.get("ECNU_API_KEY")
    if not api_key:
        print("ECNU_API_KEY is required. Set it in the local environment; do not pass it on the command line.", file=sys.stderr)
        return 2

    selected = [case for case in build_cases() if case.profiles & profiles]
    if args.case_ids:
        requested = set(args.case_ids)
        available = {case.case_id for case in selected}
        unknown = requested - available
        if unknown:
            parser.error(
                "--case is not in the selected profile: " + ", ".join(sorted(unknown))
            )
        selected = [case for case in selected if case.case_id in requested]
    budget = CreditBudget(args.max_credits, planned=sum(case.estimated_credits for case in selected))
    with temporary_artifacts() as artifact_dir:
        context = RunContext(api_key, args.timeout, artifact_dir, budget)
        records = [run_one(context, case) for case in selected]
        context.state.clear()

    report = {
        "schema_version": 1,
        "environment": {
            "tested_at_utc": utc_now(),
            "test_timezone": "UTC",
            "os": platform.system(),
            "os_release": platform.release(),
            "python_version": platform.python_version(),
            "openai_version": package_version("openai"),
            "anthropic_version": package_version("anthropic"),
            "langchain_openai_version": package_version("langchain-openai"),
            "requests_version": package_version("requests"),
            "httpx_version": package_version("httpx"),
            "account_type": redact_text(args.account_type, (api_key,))[:100],
            "network_environment": redact_text(args.network_environment, (api_key,))[:100],
        },
        "profiles": sorted(profiles),
        "official_hosts": {"openai_base": OPENAI_BASE, "anthropic_messages": ANTHROPIC_MESSAGES_URL, "service_status": STATUS_URL},
        "budget": {
            "max_credits": budget.limit,
            "planned_credits": round(budget.planned, 4),
            "reserved_credits": round(budget.reserved, 4),
            "estimated_consumed_credits": round(context.estimated_consumed_credits, 8),
            "estimation_policy": "fixed prices plus conservative small-dialog allowances; reserve before request",
            "budget_stop_triggered": budget.exhausted,
        },
        "cases": records,
        "notes": [
            "Requests were serial and POST retries were disabled.",
            "Reports omit prompts, outputs, reasoning text, media, authorization, and one-time URLs.",
            "A visible model is not proof of endpoint capability.",
        ],
    }
    output_text = json.dumps(report, ensure_ascii=False, indent=2)
    print(output_text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_text + "\n", encoding="utf-8")

    if args.strict:
        specs = {case.case_id: case for case in selected}
        failures = strict_failure_ids(records, specs, set(args.case_ids or []))
        if failures:
            print("Strict checks failed: " + ", ".join(failures), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
