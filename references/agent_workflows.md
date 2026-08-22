# Agent Workflows and Safety Rules

This document adds execution-oriented guidance for agents using the ECNU API skill.

## Implementation workflow

When asked to write an integration:

1. Identify the protocol first:
   - OpenAI-compatible APIs use `/open/api/v1`.
   - Anthropic-compatible APIs use `/open/api/anthropic`.
2. Select only documented request fields.
3. Prefer the smallest working example before adding advanced features.
4. Validate the response shape before assuming compatibility.

## Debugging workflow

For API failures collect:

- HTTP status code
- response body shape
- request endpoint
- sanitized request fields
- model name

Do not retry unchanged credentials for `401`.
Do not treat an empty `/models` response as proof of successful authentication.

## Model discovery

Runtime model discovery and documentation are different sources:

1. Documentation defines supported contracts.
2. `/models` shows runtime visibility.
3. Capability probes are required before relying on undocumented models.

A model appearing in `/models` does not guarantee that all endpoints support it.

## LangChain embedding rules

For `ecnu-embedding-small`:

- Disable LangChain token length conversion with `check_embedding_ctx_length=False`.
- Do not send unsupported OpenAI embedding parameters.
- Verify output vector length after the response.

## Cost and privacy boundaries

Before executing real API calls:

- Do not ask users to paste API keys into chat.
- Do not execute billable operations when the user only requested code examples.
- Warn before sending private documents, images, or sensitive content to the API.
- Never include API keys in logs or examples.

## Known deviations

Known service behavior differences should be recorded separately from documented contracts.
When documentation and live behavior differ, label the result as:

- documented
- observed
- unsupported or unknown
