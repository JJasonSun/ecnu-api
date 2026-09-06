from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import smoke_test  # noqa: E402


class FakeResponse:
    def __init__(self, body: bytes = b"", lines: list[bytes] | None = None, headers=None):
        self.status = 200
        self.headers = headers or {"content-type": "application/json"}
        self._body = io.BytesIO(body)
        self._lines = list(lines or [])
        self.readline_calls = 0

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def readline(self, size: int = -1) -> bytes:
        self.readline_calls += 1
        return self._lines.pop(0) if self._lines else b""

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, *args):  # type: ignore[no-untyped-def]
        return None


class RedactionTest(unittest.TestCase):
    def test_redacts_exact_key_shaped_bearer_base64_and_url(self) -> None:
        secret = "test-secret-value"
        key_shaped = "sk-" + ("a" * 32)
        encoded = "A" * 200
        text = (
            "Authori" + "zation: " + "Bear" + f"er {secret}; key={key_shaped}; "
            f"data:image/png;base64,{encoded}; "
            "url=https://download.example.test/once?ticket=secret"
        )
        redacted = smoke_test.redact_text(text, (secret,))
        for forbidden in (secret, key_shaped, encoded, "ticket=secret"):
            self.assertNotIn(forbidden, redacted)
        self.assertIn("[REDACTED_API_KEY]", redacted)
        self.assertIn("[REDACTED_BASE64_DATA]", redacted)
        self.assertIn("[REDACTED_URL]", redacted)

    def test_reasoning_is_presence_and_length_only(self) -> None:
        reasoning = "private hidden reasoning"
        sanitized = smoke_test.sanitize_value(
            {"reasoning_content": reasoning, "content": "bounded error"}
        )
        self.assertNotIn("reasoning_content", sanitized)
        self.assertTrue(sanitized["reasoning_content_present"])
        self.assertEqual(sanitized["reasoning_content_length"], len(reasoning))
        self.assertNotIn(reasoning, json.dumps(sanitized))

    def test_allowlisted_headers_exclude_auth_and_cookies(self) -> None:
        headers = smoke_test.extract_important_headers(
            {
                "Content-Type": "application/json",
                "X-Request-ID": "request-1",
                "Content-Disposition": 'attachment; filename="private prompt.mp3"',
                "Authorization": "Bearer " + "test-secret",
                "Set-Cookie": "session=secret",
                "Server": "private-proxy",
            }
        )
        self.assertEqual(
            headers,
            {"content-type": "application/json", "x-request-id": "request-1"},
        )

    def test_error_echoes_are_reduced_to_presence_and_length(self) -> None:
        private = "private prompt text"
        body = json.dumps(
            {
                "detail": {
                    "messages": [{"content": private}],
                    "input": private,
                    "query": private,
                    "documents": [private],
                    "image_url": "data:image/png;base64," + "A" * 200,
                    "data": private,
                    "body": private,
                    "payload": private,
                    "arguments": private,
                }
            }
        ).encode()
        sample = smoke_test.bounded_error_sample(body)
        self.assertNotIn(private, sample)
        for field in (
            "messages",
            "input",
            "query",
            "documents",
            "image_url",
            "data",
            "body",
            "payload",
            "arguments",
        ):
            self.assertIn(field + "_length", sample)
    def test_error_sample_is_bounded_and_redacted_for_text_and_json(self) -> None:
        secret = "test-secret-value"
        text_sample = smoke_test.bounded_error_sample(
            (secret + " " + "x" * 5000).encode(), (secret,)
        )
        self.assertNotIn(secret, text_sample)
        self.assertLessEqual(len(text_sample), smoke_test.MAX_ERROR_TEXT)

        reasoning = "do not persist this reasoning"
        json_sample = smoke_test.bounded_error_sample(
            json.dumps(
                {
                    "detail": {
                        "reasoning_content": reasoning,
                        "Authorization": "Bearer " + "test-hidden",
                    }
                }
            ).encode()
        )
        self.assertNotIn(reasoning, json_sample)
        self.assertNotIn("Bearer " + "test-hidden", json_sample)
        self.assertIn("reasoning_content_length", json_sample)

    def test_success_chat_summary_omits_content_and_reasoning_text(self) -> None:
        content = "ECNU_OK secret output"
        reasoning = "hidden chain"
        response = smoke_test.HttpResult(
            200,
            {"content-type": "application/json"},
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": content,
                                "reasoning_content": reasoning,
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 1},
                }
            ).encode(),
        )
        summary = smoke_test.summarize_response("chat", response)
        rendered = json.dumps(summary)
        self.assertNotIn(content, rendered)
        self.assertNotIn(reasoning, rendered)
        self.assertEqual(summary["content_length"], len(content))
        self.assertEqual(summary["reasoning_content_length"], len(reasoning))

    def test_backend_model_path_is_not_retained(self) -> None:
        summary = smoke_test._summarize_embedding(
            {
                "model": "/" + "root/cache/backend-model",
                "data": [{"index": 0, "embedding": [0.0] * 1024}],
            }
        )
        self.assertEqual(summary["model"], "[REDACTED_BACKEND_PATH]")


class DefaultsTest(unittest.TestCase):
    def test_environment_does_not_override_credit_cap(self) -> None:
        with patch.dict(smoke_test.os.environ, {"MAX_TEST_CREDITS": "999"}):
            self.assertEqual(smoke_test._default_max_credits(), smoke_test.DEFAULT_MAX_CREDITS)


class EmbeddingContractTest(unittest.TestCase):
    def test_embedding_payload_has_only_model_and_string_input(self) -> None:
        for input_value in ("one", ["one", "two"]):
            payload = smoke_test.build_embedding_payload(input_value)
            self.assertEqual(set(payload), {"model", "input"})
            self.assertNotIn("dimensions", payload)
            if isinstance(payload["input"], list):
                self.assertTrue(all(isinstance(item, str) for item in payload["input"]))
            else:
                self.assertIsInstance(payload["input"], str)

    def test_embedding_payload_rejects_empty_and_token_ids(self) -> None:
        with self.assertRaises(ValueError):
            smoke_test.build_embedding_payload("")
        with self.assertRaises(TypeError):
            smoke_test.build_embedding_payload([])
        with self.assertRaises(TypeError):
            smoke_test.build_embedding_payload([1, 2])  # type: ignore[arg-type]

    @unittest.skipUnless(
        importlib.util.find_spec("httpx")
        and importlib.util.find_spec("langchain_openai"),
        "optional LangChain dependencies are not installed",
    )
    def test_langchain_mock_transport_sends_strings_without_dimensions(self) -> None:
        shape, attempts = smoke_test.run_langchain_mock_capture()
        self.assertEqual(attempts, 1)
        self.assertTrue(shape["input_is_string_array"])
        self.assertFalse(shape["dimensions_present"])
        self.assertEqual(shape["vector_lengths"], [1024, 1024])


class TransportBudgetAndCleanupTest(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("httpx"), "httpx is not installed")
    def test_sdk_transport_bounds_response_before_client_parse(self) -> None:
        import httpx

        inner = httpx.MockTransport(
            lambda request: httpx.Response(200, stream=httpx.ByteStream(b"x" * 11))
        )
        transport = smoke_test.RecordingHttpxTransport(inner)
        client = httpx.Client(transport=transport)
        try:
            with patch.object(smoke_test, "MAX_RESPONSE_BYTES", 10):
                response = client.get("https://example.test/test")
        finally:
            client.close()
        self.assertEqual(response.content, b"x" * 10)
        self.assertTrue(transport.response_limit_exceeded)

    def test_post_transport_failure_is_not_retried(self) -> None:
        with patch.object(
            smoke_test, "_open_api_request", side_effect=URLError("offline")
        ) as mocked:
            result = smoke_test.request(
                "POST",
                smoke_test.OPENAI_BASE + "/chat/completions",
                payload={"model": "ecnu-plus"},
            )
        self.assertEqual(mocked.call_count, 1)
        self.assertIsNone(result.status)
        self.assertIn("URLError", result.transport_error or "")

    def test_stream_stops_at_done_without_reading_to_eof(self) -> None:
        response = FakeResponse(
            lines=[
                b'data: {"choices":[{"delta":{"content":"ok"}}]}\n',
                b"data: [DONE]\n",
                b"data: must-not-be-read\n",
            ],
            headers={"content-type": "text/event-stream"},
        )
        with patch.object(smoke_test, "_open_api_request", return_value=response):
            result = smoke_test.stream_request(
                smoke_test.OPENAI_BASE + "/chat/completions",
                headers={},
                payload={"stream": True},
                timeout=1.0,
            )
        self.assertEqual(response.readline_calls, 2)
        self.assertTrue(result.body.endswith(b"[DONE]\n"))
        self.assertNotIn(b"must-not-be-read", result.body)

    def test_stream_event_and_wall_caps_are_inconclusive(self) -> None:
        response = FakeResponse(
            lines=[b"data: {}\n", b"data: {}\n"],
            headers={"content-type": "text/event-stream"},
        )
        with patch.object(smoke_test, "MAX_STREAM_EVENTS", 1), patch.object(
            smoke_test, "_open_api_request", return_value=response
        ):
            result = smoke_test.stream_request(
                smoke_test.OPENAI_BASE + "/chat/completions",
                headers={},
                payload={"stream": True},
                timeout=1.0,
            )
        self.assertIn("event limit", result.transport_error or "")

        wall_response = FakeResponse(lines=[b"data: {}\n"])
        with patch.object(smoke_test.time, "monotonic", side_effect=[0.0, 2.0]), patch.object(
            smoke_test, "_open_api_request", return_value=wall_response
        ):
            result = smoke_test.stream_request(
                smoke_test.OPENAI_BASE + "/chat/completions",
                headers={},
                payload={"stream": True},
                timeout=1.0,
            )
        self.assertIn("wall-time", result.transport_error or "")

    def test_non_finite_credit_limits_are_rejected(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError):
                smoke_test.CreditBudget(value)
        for value in ("nan", "inf", "-inf"):
            with patch.object(sys, "stderr", new=io.StringIO()), self.assertRaises(SystemExit):
                smoke_test.main(["--max-credits=" + value])
            with patch.object(sys, "stderr", new=io.StringIO()), self.assertRaises(SystemExit):
                smoke_test.main(["--timeout=" + value])

    def test_api_redirect_handler_never_forwards_request(self) -> None:
        handler = smoke_test._NoRedirect()
        self.assertIsNone(
            handler.redirect_request(None, None, 307, "redirect", {}, "https://other.test")
        )

    def test_budget_reserves_before_calls_and_stops_at_limit(self) -> None:
        budget = smoke_test.CreditBudget(limit=5.0, planned=10.0)
        self.assertTrue(budget.reserve(3.0))
        self.assertFalse(budget.reserve(3.0))
        self.assertEqual(budget.reserved, 3.0)
        self.assertTrue(budget.exhausted)
        self.assertTrue(budget.reserve(0.0))

        exact = smoke_test.CreditBudget(limit=5.0)
        self.assertTrue(exact.reserve(5.0))
        self.assertFalse(exact.exhausted)
        self.assertFalse(exact.reserve(0.1))
        self.assertTrue(exact.exhausted)

    def test_authenticated_429_stops_later_cases(self) -> None:
        first = smoke_test._case(
            "first",
            ("core",),
            "test",
            smoke_test.OPENAI_BASE + "/test",
            "ecnu-plus",
            {},
            "test",
            "generic",
            (200,),
            custom_executor=lambda context, spec: smoke_test.Execution(
                smoke_test.HttpResult(429, {"content-type": "application/json"}, b"{}"),
                "mock",
            ),
        )
        second_called = False

        def second_executor(context, spec):  # type: ignore[no-untyped-def]
            nonlocal second_called
            second_called = True
            return smoke_test.Execution(smoke_test.HttpResult(200, {}, b"{}"), "mock")

        second = smoke_test._case(
            "second",
            ("core",),
            "test",
            smoke_test.OPENAI_BASE + "/test",
            "ecnu-plus",
            {},
            "test",
            "generic",
            (200,),
            custom_executor=second_executor,
        )
        with smoke_test.temporary_artifacts() as directory:
            context = smoke_test.RunContext(
                "test-key", 1.0, directory, smoke_test.CreditBudget(10.0)
            )
            smoke_test.run_one(context, first)
            record = smoke_test.run_one(context, second)
        self.assertFalse(second_called)
        self.assertEqual(record["result"], "skipped")
        self.assertIn("HTTP 429", record["notes"][0])

    def test_429_from_invalid_probe_stops_every_later_case(self) -> None:
        invalid = next(
            case for case in smoke_test.build_cases() if case.case_id == "models_invalid_token"
        )
        invalid = replace(
            invalid,
            custom_executor=lambda context, spec: smoke_test.Execution(
                smoke_test.HttpResult(429, {"content-type": "application/json"}, b"{}"),
                "mock",
            ),
        )
        later = next(
            case for case in smoke_test.build_cases() if case.case_id == "models_missing_auth"
        )
        called = False

        def execute_later(context, spec):  # type: ignore[no-untyped-def]
            nonlocal called
            called = True
            return smoke_test.Execution(smoke_test.HttpResult(200, {}, b"{}"), "mock")

        later = replace(later, custom_executor=execute_later)
        with smoke_test.temporary_artifacts() as directory:
            context = smoke_test.RunContext(
                "test-key", 1.0, directory, smoke_test.CreditBudget(10.0)
            )
            smoke_test.run_one(context, invalid)
            record = smoke_test.run_one(context, later)
        self.assertFalse(called)
        self.assertEqual(record["result"], "skipped")
        self.assertIn("global stop", record["notes"][0])

    def test_case_specific_401_requires_prior_valid_auth(self) -> None:
        spec = next(
            case
            for case in smoke_test.build_cases()
            if case.case_id == "error_unsupported_model"
        )
        response = smoke_test.Execution(
            smoke_test.HttpResult(
                401,
                {"content-type": "application/json"},
                b'{"detail":"metadata failure"}',
            ),
            "mock",
        )
        with smoke_test.temporary_artifacts() as directory:
            context = smoke_test.RunContext(
                "test-key", 1.0, directory, smoke_test.CreditBudget(10.0)
            )
            with patch.object(smoke_test, "raw_executor", return_value=response):
                record = smoke_test.run_one(context, spec)
        self.assertEqual(record["result"], "mismatch")
        self.assertIn("HTTP 401", context.stop_reason or "")

        with smoke_test.temporary_artifacts() as directory:
            context = smoke_test.RunContext(
                "test-key", 1.0, directory, smoke_test.CreditBudget(10.0)
            )
            context.state["valid_auth_observed"] = True
            with patch.object(smoke_test, "raw_executor", return_value=response):
                smoke_test.run_one(context, spec)
        self.assertIsNone(context.stop_reason)

    def test_unexpected_transport_attempt_stops_and_counts_allowance(self) -> None:
        first = smoke_test._case(
            "retrying",
            ("core",),
            "test",
            smoke_test.OPENAI_BASE + "/test",
            "ecnu-plus",
            {},
            "one attempt",
            "generic",
            (200,),
            cost=0.25,
            custom_executor=lambda context, spec: smoke_test.Execution(
                smoke_test.HttpResult(200, {"content-type": "application/json"}, b"{}"),
                "mock",
                attempts=2,
            ),
        )
        second = replace(first, case_id="later")
        with smoke_test.temporary_artifacts() as directory:
            context = smoke_test.RunContext(
                "test-key", 1.0, directory, smoke_test.CreditBudget(10.0)
            )
            first_record = smoke_test.run_one(context, first)
            second_record = smoke_test.run_one(context, second)
        self.assertEqual(first_record["result"], "mismatch")
        self.assertEqual(
            first_record["actual_response_shape"]["estimated_consumed_credits"],
            0.5,
        )
        self.assertEqual(second_record["result"], "skipped")
        self.assertIn("more than once", second_record["notes"][0])

    def test_unattempted_preflight_skip_releases_reservation(self) -> None:
        skipped = smoke_test._case(
            "unavailable",
            ("core",),
            "test",
            smoke_test.OPENAI_BASE + "/test",
            "ecnu-plus",
            {},
            "optional dependency",
            "generic",
            (200,),
            cost=1.0,
            custom_executor=lambda context, spec: smoke_test.SkipExecution(
                "dependency missing"
            ),
        )
        executed = replace(
            skipped,
            case_id="available",
            custom_executor=lambda context, spec: smoke_test.Execution(
                smoke_test.HttpResult(200, {"content-type": "application/json"}, b"{}"),
                "mock",
            ),
        )
        with smoke_test.temporary_artifacts() as directory:
            context = smoke_test.RunContext(
                "test-key", 1.0, directory, smoke_test.CreditBudget(1.0)
            )
            skipped_record = smoke_test.run_one(context, skipped)
            executed_record = smoke_test.run_one(context, executed)
        self.assertEqual(skipped_record["result"], "skipped")
        self.assertEqual(executed_record["result"], "pass")
        self.assertEqual(context.budget.reserved, 1.0)

    def test_temporary_artifacts_are_removed_on_exception(self) -> None:
        directory = None
        with self.assertRaises(RuntimeError):
            with smoke_test.temporary_artifacts() as temporary:
                directory = temporary
                (temporary / "media.bin").write_bytes(b"media")
                raise RuntimeError("stop")
        self.assertIsNotNone(directory)
        self.assertFalse(directory.exists())  # type: ignore[union-attr]


class PreflightMatcherTest(unittest.TestCase):
    @staticmethod
    def case(case_id: str):  # type: ignore[no-untyped-def]
        return next(case for case in smoke_test.build_cases() if case.case_id == case_id)

    def test_models_valid_rejects_empty_ids(self) -> None:
        spec = self.case("models_valid")
        self.assertFalse(
            smoke_test.case_response_matches(
                spec, 200, {"valid_json": True, "model_ids": []}
            )
        )

    def test_expected_errors_require_json_and_tts_error_structure(self) -> None:
        generic = self.case("error_missing_model")
        text_shape = smoke_test.summarize_response(
            "generic",
            smoke_test.HttpResult(422, {"content-type": "text/plain"}, b"invalid"),
        )
        self.assertFalse(smoke_test.case_response_matches(generic, 422, text_shape))

        tts = self.case("tts_invalid_voice")
        empty_json = smoke_test.summarize_response(
            "generic",
            smoke_test.HttpResult(400, {"content-type": "application/json"}, b"{}"),
        )
        detail_json = smoke_test.summarize_response(
            "generic",
            smoke_test.HttpResult(
                400,
                {"content-type": "application/json"},
                b'{"detail":"invalid voice"}',
            ),
        )
        documented_json = smoke_test.summarize_response(
            "generic",
            smoke_test.HttpResult(
                400,
                {"content-type": "application/json"},
                b'{"error":"invalid voice","request_id":"test","details":{}}',
            ),
        )
        self.assertFalse(smoke_test.case_response_matches(tts, 400, empty_json))
        self.assertFalse(smoke_test.case_response_matches(tts, 400, detail_json))
        self.assertTrue(smoke_test.case_response_matches(tts, 400, documented_json))

    def test_max_1m_401_is_local_and_plain_max_fallback_runs(self) -> None:
        suffix = replace(
            self.case("anthropic_max_1m"),
            custom_executor=lambda context, spec: smoke_test.Execution(
                smoke_test.HttpResult(
                    401, {"content-type": "application/json"}, b'{"detail":"suffix"}'
                ),
                "mock",
            ),
        )
        fallback_body = json.dumps(
            {
                "model": "ecnu-max",
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        ).encode()
        fallback = replace(
            self.case("anthropic_max_1m_fallback_plain_max"),
            custom_executor=lambda context, spec: smoke_test.Execution(
                smoke_test.HttpResult(
                    200, {"content-type": "application/json"}, fallback_body
                ),
                "mock",
            ),
        )
        with smoke_test.temporary_artifacts() as directory:
            context = smoke_test.RunContext(
                "test-key", 1.0, directory, smoke_test.CreditBudget(10.0)
            )
            fallback_record = smoke_test.run_one(context, fallback)
            suffix_record = smoke_test.run_one(context, suffix)
        self.assertEqual(fallback_record["result"], "pass")
        self.assertEqual(suffix_record["result"], "mismatch")
        self.assertIsNone(context.stop_reason)

    def test_tts_requires_audio_disposition_and_pcm_headers(self) -> None:
        pcm = self.case("tts_xiayu_pcm")
        missing = smoke_test.summarize_response(
            "tts",
            smoke_test.HttpResult(200, {"content-type": "audio/pcm"}, b"pcm"),
        )
        complete = smoke_test.summarize_response(
            "tts",
            smoke_test.HttpResult(
                200,
                {
                    "content-type": "audio/pcm",
                    "content-disposition": "attachment",
                    "content-rate": "24000",
                    "content-channels": "1",
                    "content-bits": "16",
                },
                b"pcm",
            ),
        )
        self.assertFalse(smoke_test.case_response_matches(pcm, 200, missing))
        self.assertTrue(smoke_test.case_response_matches(pcm, 200, complete))

    def test_image_requires_verified_mime_dimensions_and_hash(self) -> None:
        spec = self.case("image_generation_documented")
        good = {
            "data_count": 1,
            "media_verified": True,
            "media_content_type": "image/png",
            "pixel_dimensions": [512, 512],
            "sha256": "a" * 64,
        }
        self.assertTrue(smoke_test.case_response_matches(spec, 200, good))
        for key in ("media_verified", "media_content_type", "pixel_dimensions", "sha256"):
            broken = dict(good)
            broken.pop(key)
            self.assertFalse(smoke_test.case_response_matches(spec, 200, broken))

    def test_private_dns_and_redirect_targets_are_rejected(self) -> None:
        private_info = [(2, 1, 6, "", ("127.0.0.1", 443))]
        with patch.object(smoke_test.socket, "getaddrinfo", return_value=private_info):
            self.assertIsNone(
                smoke_test._resolve_public_https("https://private.test/image.png")
            )
        self.assertFalse(smoke_test._public_ip("224.0.0.1"))
        self.assertFalse(smoke_test._public_ip("64:ff9b::7f00:1"))

        public = "https://public.test/image.png"
        redirect = smoke_test.HttpResult(
            302, {"location": "https://private.test/image.png"}, b""
        )
        with patch.object(
            smoke_test,
            "_resolve_public_https",
            side_effect=[(smoke_test.urlsplit(public), "93.184.216.34"), None],
        ), patch.object(smoke_test, "_pinned_https_get", return_value=redirect) as get:
            result = smoke_test.fetch_public_image(
                public, 1.0
            )
        self.assertEqual(get.call_count, 1)
        self.assertIn("public HTTPS", result.transport_error or "")

    def test_image_download_bytes_are_bounded(self) -> None:
        body, exceeded = smoke_test._read_bounded(io.BytesIO(b"x" * 11), 10)
        self.assertEqual(len(body), 10)
        self.assertTrue(exceeded)

    def test_image_integrity_requires_complete_valid_png(self) -> None:
        valid = smoke_test.make_test_png()
        self.assertEqual(smoke_test._image_dimensions(valid), [16, 16])
        self.assertEqual(smoke_test._image_mime(valid), "image/png")
        self.assertIsNone(smoke_test._image_dimensions(valid[:24]))
        corrupted = bytearray(valid)
        corrupted[-5] ^= 1
        self.assertIsNone(smoke_test._image_mime(bytes(corrupted)))
        header = smoke_test.struct.pack(
            ">IIBBBBB", 512, 512, 8, 6, 0, 0, 0
        )
        forged = (
            b"\x89PNG\r\n\x1a\n"
            + smoke_test._png_chunk(b"IHDR", header)
            + smoke_test._png_chunk(b"IDAT", smoke_test.zlib.compress(b"x"))
            + smoke_test._png_chunk(b"IEND", b"")
        )
        self.assertIsNone(smoke_test._image_dimensions(forged))

    def test_usage_counters_and_official_credit_formula_are_retained(self) -> None:
        spec = self.case("chat_basic_ecnu_max")
        shape = {
            "usage_counters": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "prompt_tokens_details": {"cached_tokens": 20},
            }
        }
        credits, basis = smoke_test.estimate_consumed_credits(spec, 200, shape)
        self.assertAlmostEqual(credits, 0.0372)
        self.assertIn("ecnu-max", basis)

        sdk_embedding = self.case("openai_sdk_embedding")
        fixed, fixed_basis = smoke_test.estimate_consumed_credits(
            sdk_embedding, 200, {"usage_counters": {"prompt_tokens": 5}}
        )
        self.assertEqual(fixed, 0.05)
        self.assertIn("embedding", fixed_basis)

        response = smoke_test.HttpResult(
            200,
            {"content-type": "application/json"},
            json.dumps(
                {
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": shape["usage_counters"],
                }
            ).encode(),
        )
        summary = smoke_test.summarize_response("chat", response)
        self.assertEqual(summary["usage_counters"], shape["usage_counters"])

    def test_compatibility_vision_is_unverified_and_behavior_checked(self) -> None:
        for case_id in (
            "responses_max_vision_compatibility",
            "anthropic_max_vision_compatibility",
        ):
            spec = self.case(case_id)
            self.assertTrue(spec.documented_expectation.startswith("Not documented"))
            base = {
                "output_count": 1,
                "output_text_present": True,
                "usage_keys": ["input_tokens"],
            } if case_id.startswith("responses") else {
                "content_count": 1,
                "text_present": True,
            }
            self.assertFalse(smoke_test.case_response_matches(spec, 200, base))
            self.assertTrue(
                smoke_test.case_response_matches(
                    spec, 200, {**base, "vision_behavior": "strip-image"}
                )
            )

    def test_thinking_tool_and_anthropic_alias_invariants(self) -> None:
        tool = self.case("chat_thinking_tool_first")
        shape = {
            "tool_call_count": 1,
            "tool_names": ["echo"],
            "tool_arguments_json_valid": [True],
            "tool_ping_argument": [True],
        }
        self.assertFalse(smoke_test.case_response_matches(tool, 200, shape))
        self.assertTrue(
            smoke_test.case_response_matches(
                tool, 200, {**shape, "reasoning_content_present": True}
            )
        )
        alias = self.case("anthropic_sonnet_mapping")
        alias_shape = {"content_count": 1, "text_present": True, "model": "ecnu-max"}
        self.assertFalse(smoke_test.case_response_matches(alias, 200, alias_shape))
        self.assertTrue(
            smoke_test.case_response_matches(
                alias, 200, {**alias_shape, "model": "claude-sonnet-4-20250514"}
            )
        )
        self.assertTrue(
            smoke_test.case_response_matches(
                alias, 200, {**alias_shape, "model": "ecnu-plus"}
            )
        )
        opus = self.case("anthropic_opus_mapping")
        self.assertFalse(
            smoke_test.case_response_matches(
                opus, 200, {**alias_shape, "model": "ecnu-plus"}
            )
        )
        self.assertTrue(
            smoke_test.case_response_matches(
                opus, 200, {**alias_shape, "model": "ecnu-max"}
            )
        )

    def test_effort_invariants_and_anthropic_bearer_only(self) -> None:
        none = self.case("responses_max_effort_none")
        low = self.case("responses_max_effort_low")
        base = {
            "output_count": 1,
            "output_text_present": True,
            "usage_keys": ["input_tokens"],
        }
        self.assertTrue(smoke_test.case_response_matches(none, 200, base))
        self.assertFalse(smoke_test.case_response_matches(low, 200, base))
        self.assertTrue(
            smoke_test.case_response_matches(
                low, 200, {**base, "reasoning_content_present": True}
            )
        )
        headers = smoke_test._headers("anthropic", "test-key") or {}
        self.assertIn("Authorization", headers)
        self.assertNotIn("x-api-key", headers)

    def test_selected_sdk_cases_are_strict_required(self) -> None:
        selected = [
            case
            for case in smoke_test.build_cases()
            if "SDK" in case.protocol or "LangChain" in case.protocol
        ]
        self.assertTrue(selected)
        self.assertTrue(all(case.required for case in selected))

    def test_langchain_cases_require_exact_wire_and_vector_shapes(self) -> None:
        wire = self.case("langchain_embedding_wire_capture")
        valid_wire = {
            "input_is_string_array": True,
            "dimensions_present": False,
            "vector_count": 2,
            "vector_lengths": [1024, 1024],
        }
        self.assertTrue(smoke_test.case_response_matches(wire, 200, valid_wire))
        self.assertFalse(
            smoke_test.case_response_matches(
                wire, 200, {**valid_wire, "dimensions_present": True}
            )
        )
        live = self.case("langchain_embedding_live")
        valid_live = {
            "count": 1,
            "dimensions_present": False,
            "vector_lengths": [1024],
        }
        self.assertTrue(smoke_test.case_response_matches(live, 200, valid_live))
        self.assertFalse(
            smoke_test.case_response_matches(
                live, 200, {**valid_live, "vector_lengths": []}
            )
        )

    def test_rerank_requires_nonempty_indexed_numeric_results(self) -> None:
        spec = self.case("rerank_default")
        valid = {
            "result_count": 3,
            "indexes": [0, 1, 2],
            "score_types": ["float", "float", "float"],
        }
        self.assertTrue(smoke_test.case_response_matches(spec, 200, valid))
        for invalid in (
            {"result_count": 0, "indexes": [], "score_types": []},
            {**valid, "indexes": []},
            {**valid, "score_types": ["str", "str", "str"]},
        ):
            self.assertFalse(smoke_test.case_response_matches(spec, 200, invalid))

    def test_direct_plus_vision_requires_image_understanding(self) -> None:
        spec = self.case("vision_direct_ecnu_plus")
        base = {"choice_count": 1, "content_present": True}
        self.assertFalse(smoke_test.case_response_matches(spec, 200, base))
        self.assertFalse(
            smoke_test.case_response_matches(
                spec, 200, {**base, "vision_behavior": "ignore-image"}
            )
        )
        self.assertTrue(
            smoke_test.case_response_matches(
                spec, 200, {**base, "vision_behavior": "accept"}
            )
        )


class StructuredOutputTest(unittest.TestCase):
    @staticmethod
    def shape(kind: str, content: str, finish_reason: str | None = "stop"):
        response = smoke_test.HttpResult(
            200,
            {"content-type": "application/json"},
            json.dumps(
                {
                    "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                }
            ).encode(),
        )
        return smoke_test.summarize_response(kind, response)

    def test_matrix_covers_both_models_and_formats(self) -> None:
        cases = [case for case in smoke_test.build_cases() if case.case_id.startswith("structured_output_")]
        matrix = set()
        for case in cases:
            payload = case.payload_factory(None)
            response_format = payload["response_format"]
            matrix.add((payload["model"], response_format["type"]))
            self.assertEqual(case.profiles, frozenset({"core"}))
            self.assertEqual(payload["max_tokens"], 128)
            self.assertIn("Markdown", payload["messages"][0]["content"])
            if response_format["type"] == "json_schema":
                self.assertEqual(response_format["json_schema"]["schema"], smoke_test.STRUCTURED_SCHEMA)
                self.assertEqual(case.response_kind, "structured")
            else:
                self.assertEqual(response_format, {"type": "json_object"})
                self.assertEqual(case.response_kind, "structured_object")
        self.assertEqual(len(cases), 4)
        self.assertEqual(
            matrix,
            {(model, kind) for model in ("ecnu-plus", "ecnu-max") for kind in ("json_schema", "json_object")},
        )

    def test_schema_checks_fields_but_not_semantic_correctness(self) -> None:
        content = '{"name":"wrong name","department":"wrong department"}'
        shape = self.shape("structured", content)
        self.assertTrue(smoke_test.response_matches("structured", 200, shape))
        self.assertFalse(shape["semantic_match"])
        self.assertNotIn("wrong name", json.dumps(shape))
        for content in ('{}', '{"name":"n"}', '{"name":1,"department":"d"}', '{"name":"n","department":"d","extra":true}'):
            with self.subTest(content=content):
                shape = self.shape("structured", content)
                self.assertFalse(smoke_test.response_matches("structured", 200, shape))

    def test_json_object_does_not_require_schema_fields(self) -> None:
        for content in ('{}', '{"arbitrary":[1,true,null]}'):
            with self.subTest(content=content):
                shape = self.shape("structured_object", content)
                self.assertTrue(smoke_test.response_matches("structured_object", 200, shape))
                for field in ("schema_valid", "required_fields_valid", "additional_property_count", "semantic_match"):
                    self.assertNotIn(field, shape)

    def test_both_formats_reject_fences_non_objects_and_invalid_json(self) -> None:
        invalid_contents = (
            '```json\n{"name":"n","department":"d"}\n```',
            '{"name":"n","department":',
            '[]',
            'null',
            '{"name":"n","department":"d","invalid":NaN}',
            '{"invalid":Infinity}',
        )
        for kind in ("structured", "structured_object"):
            for content in invalid_contents:
                with self.subTest(kind=kind, content=content):
                    shape = self.shape(kind, content)
                    self.assertFalse(shape["structured_json_valid"])
                    self.assertFalse(smoke_test.response_matches(kind, 200, shape))

    def test_valid_json_still_requires_normal_completion(self) -> None:
        content = '{"name":"n","department":"d"}'
        for kind in ("structured", "structured_object"):
            for finish_reason in ("length", "content_filter", None):
                with self.subTest(kind=kind, finish_reason=finish_reason):
                    shape = self.shape(kind, content, finish_reason)
                    self.assertTrue(shape["structured_json_valid"])
                    self.assertFalse(smoke_test.response_matches(kind, 200, shape))


class EvidenceAndProfileTest(unittest.TestCase):
    def test_case_record_has_exact_required_schema(self) -> None:
        spec = smoke_test.build_cases()[0]
        record = smoke_test.skipped_record(spec, "offline")
        self.assertEqual(tuple(record), smoke_test.CASE_FIELDS)
        self.assertEqual(record["result"], "skipped")
        self.assertEqual(record["classification"], "application-policy")

    def test_explicit_optional_skip_fails_strict_mode(self) -> None:
        spec = replace(smoke_test.build_cases()[-1], required=False)
        record = smoke_test.skipped_record(spec, "budget")
        specs = {spec.case_id: spec}
        self.assertEqual(smoke_test.strict_failure_ids([record], specs, set()), [])
        self.assertEqual(
            smoke_test.strict_failure_ids([record], specs, {spec.case_id}),
            [spec.case_id],
        )

    def test_backend_model_label_is_recorded_without_failing_chat(self) -> None:
        spec = next(
            case
            for case in smoke_test.build_cases()
            if case.case_id == "chat_basic_ecnu_plus"
        )
        shape = {
            "choice_count": 1,
            "content_present": True,
            "usage_keys": ["prompt_tokens"],
            "model": "backend-model-label",
        }
        self.assertTrue(smoke_test.case_response_matches(spec, 200, shape))

    def test_negative_embedding_and_rerank_keep_success_shapes(self) -> None:
        cases = {case.case_id: case for case in smoke_test.build_cases()}
        self.assertEqual(cases["embedding_8193_chars"].response_kind, "embedding")
        self.assertEqual(cases["rerank_document_8193"].response_kind, "rerank")
        self.assertEqual(
            cases["langchain_embedding_wire_capture"].evidence_classification,
            "application-policy",
        )

    def test_anthropic_alias_budget_uses_effective_model(self) -> None:
        cases = {case.case_id: case for case in smoke_test.build_cases()}
        self.assertEqual(cases["anthropic_sonnet_mapping"].estimated_credits, 0.04)
        self.assertEqual(cases["anthropic_opus_mapping"].estimated_credits, 0.08)
        self.assertEqual(smoke_test._effective_dialog_model("ecnu-reasoner"), "ecnu-max")
        self.assertEqual(
            smoke_test._effective_dialog_model("ecnu-reasoner-lite"), "ecnu-plus"
        )
        for case in cases.values():
            payload = None
            if case.payload_factory and case.case_id not in {
                "chat_thinking_tool_continue",
                "chat_thinking_tool_omit_reasoning",
            }:
                try:
                    payload = case.payload_factory(None)  # type: ignore[arg-type]
                except (AttributeError, smoke_test.CaseUnavailable):
                    payload = None
            self.assertGreaterEqual(
                case.estimated_credits + 1e-9,
                smoke_test._minimum_output_credit(case.model, payload),
                case.case_id,
            )

    def test_thinking_tool_cases_have_room_for_reasoning_and_tool_output(self) -> None:
        cases = {case.case_id: case for case in smoke_test.build_cases()}
        first = cases["chat_thinking_tool_first"].payload_factory(None)
        self.assertEqual(first["max_tokens"], 256)

    def test_matrix_contains_high_value_cases(self) -> None:
        cases = smoke_test.build_cases()
        ids = {case.case_id for case in cases}
        expected = {
            "models_valid",
            "models_invalid_token",
            "chat_stream_ecnu_plus",
            "chat_thinking_tool_continue",
            "responses_max_effort_low",
            "embedding_token_ids",
            "embedding_8193_chars",
            "rerank_top_n_over_count",
            "vision_direct_ecnu_max",
            "structured_output_ecnu_plus",
            "structured_output_ecnu_max",
            "structured_output_json_object_ecnu_plus",
            "structured_output_json_object_ecnu_max",
            "anthropic_max_1m",
            "anthropic_invalid_effort",
            "tts_xiayu_pcm",
            "tts_invalid_voice",
            "image_generation_documented",
        }
        self.assertTrue(expected <= ids, expected - ids)
        self.assertEqual(len(ids), len(cases), "case IDs must be unique")
        for case in cases:
            self.assertTrue(case.endpoint.startswith("https://chat.ecnu.edu.cn/"))

    def test_default_auth_profile_has_no_image_or_tts(self) -> None:
        parser = smoke_test.build_parser()
        args = parser.parse_args([])
        profiles = smoke_test.selected_profiles(args, parser)
        selected = [case.case_id for case in smoke_test.build_cases() if case.profiles & profiles]
        self.assertEqual(profiles, {"auth"})
        self.assertNotIn("image_generation_documented", selected)
        self.assertFalse(any(case_id.startswith("tts_") for case_id in selected))

    def test_billable_plan_prioritizes_pcm_invalid_and_one_image(self) -> None:
        selected = [
            case
            for case in smoke_test.build_cases()
            if "billable" in case.profiles and case.estimated_credits
        ]
        self.assertEqual(sum(case.estimated_credits for case in selected), 55.0)
        self.assertEqual(
            [case.case_id for case in selected[:3]],
            ["tts_xiayu_pcm", "tts_invalid_voice", "image_generation_documented"],
        )
        self.assertTrue(all(case.required for case in selected[:3]))
        self.assertTrue(all(not case.required for case in selected[3:]))
        self.assertEqual(selected[-1].case_id, "tts_extended_voice_sample")

    def test_all_profile_budget_keeps_required_billable_cases(self) -> None:
        budget = smoke_test.CreditBudget(limit=50.0)
        allowed: list[str] = []
        skipped: list[str] = []
        for case in smoke_test.build_cases():
            if budget.reserve(case.estimated_credits):
                allowed.append(case.case_id)
            elif case.estimated_credits:
                skipped.append(case.case_id)
        self.assertIn("tts_xiayu_pcm", allowed)
        self.assertIn("tts_invalid_voice", allowed)
        self.assertIn("image_generation_documented", allowed)
        self.assertIn("tts_liwa_mp3", skipped)
        self.assertIn("tts_extended_voice_sample", skipped)
        self.assertLessEqual(budget.reserved, budget.limit)

    def test_legacy_flags_map_without_enabling_billable_profile(self) -> None:
        parser = smoke_test.build_parser()
        args = parser.parse_args(["--low-cost", "--anthropic"])
        self.assertEqual(
            smoke_test.selected_profiles(args, parser),
            {"core", "compatibility"},
        )


if __name__ == "__main__":
    unittest.main()
