from __future__ import annotations

import base64
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch

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
    def test_image_edit_recipe_multipart_and_output_validation(self) -> None:
        import requests

        text = (ROOT / "references/examples.md").read_text(encoding="utf-8")
        section = text.split("## Image generation and editing\n", 1)[1].split("\n## ", 1)[0]
        code, = re.findall(r"```python\n(.*?)\n```", section, re.S)
        image_bytes = b"synthetic source image"
        edited_bytes = b"synthetic edited image"
        requests_seen = []
        bodies = [
            {"data": [{"b64_json": base64.b64encode(edited_bytes).decode()}]},
            {"err_message": "rejected", "data": [{"revised_prompt": "****"}]},
            {"data": [{"revised_prompt": "instruction only"}]},
            {"data": [{"b64_json": "not base64!"}]},
            {"data": []},
        ]

        def send(request, **kwargs):
            requests_seen.append(request)
            self.assertEqual(kwargs["timeout"], 120)
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps(body).encode()
            return response

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            source.write_bytes(image_bytes)
            with patch.dict(os.environ, {"ECNU_API_KEY": "test-key"}), \
                    patch("requests.sessions.Session.send", side_effect=send):
                for index, body in enumerate(bodies):
                    with self.subTest(body=index):
                        namespace = {"image_path": source, "prompt": "Keep the subject; change the sky"}
                        if index == 0:
                            exec(code, namespace)
                            self.assertEqual(namespace["edited_bytes"], edited_bytes)
                        else:
                            with self.assertRaises((RuntimeError, ValueError)):
                                exec(code, namespace)
                        self.assertEqual(source.read_bytes(), image_bytes)
                        self.assertEqual(len(requests_seen), index + 1)
                        self.assertTrue(namespace["source"].closed)

                for prompt in ("", " ", "x" * 1025, None):
                    with self.subTest(prompt_length=len(prompt) if prompt else 0):
                        with self.assertRaises(ValueError):
                            exec(code, {"image_path": source, "prompt": prompt})
                self.assertEqual(len(requests_seen), len(bodies))

        request = requests_seen[0]
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.url, "https://chat.ecnu.edu.cn/open/api/v1/images/edits")
        self.assertEqual(request.headers["Authorization"], "Bearer test-key")
        multipart = BytesParser(policy=policy.default).parsebytes(
            ("Content-Type: " + request.headers["Content-Type"] + "\r\n\r\n").encode()
            + request.body
        )
        fields = {part.get_param("name", header="content-disposition"): part
                  for part in multipart.iter_parts()}
        self.assertEqual(set(fields), {"model", "prompt", "response_format", "image"})
        self.assertEqual(fields["model"].get_payload(decode=True), b"ecnu-image")
        self.assertEqual(fields["prompt"].get_payload(decode=True), b"Keep the subject; change the sky")
        self.assertEqual(fields["response_format"].get_payload(decode=True), b"b64_json")
        self.assertEqual(fields["image"].get_payload(decode=True), image_bytes)

    def test_multimodal_recipe_preserves_image_objects(self) -> None:
        import requests

        text = (ROOT / "references/examples.md").read_text(encoding="utf-8")
        section = text.split("## Multimodal retrieval\n", 1)[1].split("\n## ", 1)[0]
        code, = re.findall(r"```python\n(.*?)\n```", section, re.S)
        data_url = "data:image/png;base64," + base64.b64encode(b"synthetic image").decode()
        namespace = {"image_data_url": data_url}
        exec(code, namespace)
        for name, endpoint, model in (
            ("embedding_payload", "/embeddings", "ecnu-embedding-vl"),
            ("rerank_payload", "/rerank", "ecnu-rerank-vl"),
        ):
            with self.subTest(endpoint=endpoint):
                request = requests.Request(
                    "POST", "https://example.test" + endpoint, json=namespace[name],
                ).prepare()
                body = json.loads(request.body)
                self.assertEqual(body["model"], model)
                items = body["input"] if name == "embedding_payload" else body["documents"]
                self.assertEqual(items[0], {"text": "A red flower beside a green leaf", "image": data_url})
                self.assertIsInstance(items[1], str)
                if name == "embedding_payload":
                    self.assertEqual(body["dimensions"], 1024)
                    self.assertEqual(body["encoding_format"], "float")
                else:
                    self.assertFalse(body["return_documents"])
                    self.assertEqual(body["top_n"], len(items))

    def test_documentation_can_quote_embedding_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ecnu-api"
            shutil.copytree(
                ROOT, root,
                ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".live-artifacts"),
            )
            examples = root / "references/examples.md"
            examples.write_text(
                examples.read_text(encoding="utf-8")
                + "\nThe official example uses `dimensions=1024`; acceptance is unverified.\n"
                + "Do not send `dimensions=1024` in this recipe.\n",
                encoding="utf-8",
            )
            self.assertEqual(validate_skill.collect_errors(root), [])

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
