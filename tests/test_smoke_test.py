from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import smoke_test  # noqa: E402


class SmokeTestHelpersTest(unittest.TestCase):
    def test_redact_text_removes_exact_and_key_shaped_values(self) -> None:
        secret = "test-secret-value"
        key_shaped = "sk-" + ("a" * 32)
        text = (
            "Authorization: Bearer test-secret-value "
            f"and {key_shaped}"
        )
        redacted = smoke_test.redact_text(text, (secret,))
        self.assertNotIn(secret, redacted)
        self.assertNotIn(key_shaped, redacted)
        self.assertGreaterEqual(redacted.count("[REDACTED_API_KEY]"), 2)

    def test_embedding_payload_uses_only_documented_fields(self) -> None:
        payload = smoke_test.build_embedding_payload(["one", "two"])
        self.assertEqual(
            payload,
            {
                "model": "ecnu-embedding-small",
                "input": ["one", "two"],
            },
        )

    def test_embedding_payload_rejects_token_ids(self) -> None:
        with self.assertRaises(TypeError):
            smoke_test.build_embedding_payload([1, 2])  # type: ignore[arg-type]

    def test_models_summary_keeps_structure_not_raw_body(self) -> None:
        result = smoke_test.HttpResult(
            status=200,
            headers={"content-type": "application/json"},
            body=(
                b'{"object":"list","data":['
                b'{"id":"ecnu-plus"},{"id":"ecnu-max"}]}'
            ),
        )
        summary = smoke_test.summarize_response("models_valid", result)
        self.assertEqual(summary["model_ids"], ["ecnu-plus", "ecnu-max"])
        self.assertNotIn("body", summary)

    def test_error_summary_redacts_and_bounds_text(self) -> None:
        secret = "test-secret-value"
        result = smoke_test.HttpResult(
            status=500,
            headers={"content-type": "text/plain"},
            body=(secret + " " + ("x" * 5000)).encode(),
        )
        summary = smoke_test.summarize_response(
            "other",
            result,
            secrets=(secret,),
        )
        error_text = summary["error_text"]
        self.assertNotIn(secret, error_text)
        self.assertLessEqual(len(error_text), smoke_test.MAX_ERROR_TEXT)


if __name__ == "__main__":
    unittest.main()
