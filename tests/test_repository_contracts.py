from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_skill  # noqa: E402


class RepositoryValidatorHelpersTest(unittest.TestCase):
    def test_secret_regex_covers_hyphen_and_underscore(self) -> None:
        candidate = "sk-" + ("abc_DEF-123_" * 2)
        self.assertIsNotNone(validate_skill.SECRET_RE.search(candidate))

    def test_bearer_check_allows_placeholders_and_test_values(self) -> None:
        text = "\n".join(
            [
                "Authorization: Bearer <ECNU_API_KEY>",
                '"Authorization": f"Bearer {api_key}"',
                "Authorization: Bearer test-secret-value",
                "Authorization: Bearer invalid-smoke-test-token",
            ]
        )
        self.assertEqual(validate_skill.find_literal_bearers(text), [])

    def test_bearer_check_flags_literal_without_echoing_it(self) -> None:
        text = "Authorization:" + " Bearer live-value-1234567890"
        self.assertEqual(validate_skill.find_literal_bearers(text), [1])

    def test_personal_path_check_is_cross_platform(self) -> None:
        text = "\n".join(
            [
                "/" + "Users/alice/project",
                "/" + "home/alice/project",
                "C:" + "\\Users\\alice\\project",
            ]
        )
        self.assertEqual(validate_skill.find_personal_paths(text), [1, 2, 3])
        placeholders = "/Users/<username>/project\nC:\\Users\\<username>\\project"
        self.assertEqual(validate_skill.find_personal_paths(placeholders), [])

    def test_artifact_policy_uses_dedicated_ignored_directory(self) -> None:
        forbidden = [
            Path(".env"),
            Path(".env.local"),
            Path("voice.mp3"),
            Path("smoke-results.json"),
            Path("smoke-results") / "case.json",
            Path("auth.json"),
            Path("core-2026-08-23.json"),
            Path("compatibility_alias.jsonl"),
        ]
        self.assertTrue(all(validate_skill.is_forbidden_artifact(p) for p in forbidden))
        allowed = [
            Path(".env.example"),
            Path("references/example.json"),
            Path(validate_skill.LIVE_ARTIFACT_DIR) / "voice.mp3",
        ]
        self.assertTrue(all(not validate_skill.is_forbidden_artifact(p) for p in allowed))

    def test_security_scan_covers_all_nonbinary_file_types(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (".env.example", "config.json", "check.sh", "pyproject.toml", "NOTICE"):
                (root / name).write_text("safe text", encoding="utf-8")
            (root / "binary.dat").write_bytes(b"text\x00binary")
            names = {path.name for path in validate_skill.iter_text_files(root)}
        self.assertTrue(
            {".env.example", "config.json", "check.sh", "pyproject.toml", "NOTICE"}
            <= names
        )
        self.assertNotIn("binary.dat", names)

    def test_known_deviation_schema_and_status(self) -> None:
        valid = """## Invalid token model list

- Tested at: 2026-08-23T00:00:00Z
- Environment: Python 3.11, direct HTTP, personal token
- Protocol and endpoint: OpenAI-compatible `GET /models`
- Documented expectation: authentication error
- Observed behavior: empty list
- Reproduction conditions: use an invalid synthetic token
- Impact: empty data can be mistaken for success
- Recommended fallback: reject an empty list as inconclusive
- Status: active
"""
        self.assertEqual(validate_skill.validate_known_deviations_text(valid), [])
        for status in validate_skill.ALLOWED_DEVIATION_STATUSES:
            candidate = valid.replace("Status: active", f"Status: {status}")
            self.assertEqual(validate_skill.validate_known_deviations_text(candidate), [])
        invalid = valid.replace("Status: active", "Status: permanent")
        self.assertTrue(validate_skill.validate_known_deviations_text(invalid))


class CurrentRepositoryContractsTest(unittest.TestCase):
    def test_openai_tool_recipe_preserves_returned_fields(self) -> None:
        import httpx
        from openai import OpenAI

        text = (ROOT / "references/examples.md").read_text(encoding="utf-8")
        section = text.split("## Thinking and tool history\n", 1)[1].split("\n## ", 1)[0]
        history_code, sdk_code = re.findall(r"```python\n(.*?)\n```", section, re.S)
        for extension in ({"reasoning_content": "synthetic"}, {"reasoning": {"value": "synthetic"}}, {}):
            with self.subTest(fields=list(extension)):
                original = {
                    "role": "assistant", "content": None,
                    "tool_calls": [{
                        "id": "call_test", "type": "function",
                        "function": {"name": "echo", "arguments": '{"text":"ping"}'},
                    }],
                    **extension,
                }
                requests = []

                def respond(request):
                    requests.append(json.loads(request.content))
                    return httpx.Response(200, json={
                        "id": "test-completion", "object": "chat.completion", "created": 0,
                        "model": "ecnu-max", "choices": [{
                            "index": 0,
                            "finish_reason": "tool_calls" if len(requests) == 1 else "stop",
                            "message": original if len(requests) == 1 else {
                                "role": "assistant", "content": "ping",
                            },
                        }],
                    })

                with OpenAI(
                    api_key="test-key", base_url="https://example.test/v1",
                    http_client=httpx.Client(transport=httpx.MockTransport(respond)),
                    max_retries=0,
                ) as client:
                    messages = [{"role": "user", "content": "Echo ping"}]
                    response = client.chat.completions.create(model="ecnu-max", messages=messages)
                    namespace = {"response": response, "messages": messages,
                                 "tool_results": [("call_test", "ping")]}
                    exec(sdk_code, namespace)
                    exec(history_code, namespace)
                    response = client.chat.completions.create(model="ecnu-max", messages=messages)
                    messages.append(response.choices[0].message.model_dump(mode="json", exclude_unset=True))
                    messages.append({"role": "user", "content": "What was the tool result?"})
                    client.chat.completions.create(model="ecnu-max", messages=messages)

                self.assertEqual(namespace["assistant_message"], original)
                for request in requests[1:]:
                    self.assertEqual(request["messages"][1], original)
                    self.assertEqual(request["messages"][2], {
                        "role": "tool", "tool_call_id": "call_test", "content": "ping",
                    })

    def test_agents_repository_guide_contract(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertEqual(validate_skill.validate_agents_text(text), [])

    def test_known_deviations_repository_contract(self) -> None:
        text = (ROOT / "references/known_deviations.md").read_text(encoding="utf-8")
        self.assertEqual(validate_skill.validate_known_deviations_text(text), [])

    def test_live_artifact_directory_is_ignored(self) -> None:
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertEqual(validate_skill.validate_gitignore_text(text), [])


if __name__ == "__main__":
    unittest.main()
