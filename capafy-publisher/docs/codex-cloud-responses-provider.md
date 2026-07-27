# Codex Cloud Responses Provider

## Context

Current Codex no longer supports `wire_api = "chat"`. Renaming a Chat Completions provider to `responses` does not convert its protocol, so the publisher must reject incompatible configurations instead of rewriting them into a provider that cannot run.

## Policy

When publishing Codex:

- Accept only `wire_api = "responses"` and `api_format = "openai-responses"`.
- Reject `chat` in any `[model_providers.*]` section before credentials are uploaded.
- Reject confirmed platform selections that change a Codex provider to a non-Responses API format.
- Reject official providers whose registered API format is not `openai-responses`, even if the entry is mislabeled as Responses.
- Allow custom gateways only when they expose a real OpenAI Responses-compatible endpoint.

## Official Provider Validation

Provider capability is checked using both the confirmed provider identity and an exact official base URL match. For example, DeepSeek's official endpoint is Chat Completions-compatible, so it cannot be selected directly for Codex. OpenAI and xAI official endpoints are registered as Responses-compatible.

An independent gateway that translates Responses requests to another upstream may still be used, but it must have its own provider identity and its actual Responses endpoint URL. It must not use the official identity or official URL of a completions-only provider.

## Failure Behavior

Unsupported local configuration fails during configure scanning. Unsupported changes made on the platform confirmation page fail again before confirmed provider settings are written into staging. The staging config is not silently converted.

## Non-Goals

- Do not silently rewrite the creator's source config.
- Do not claim that changing `wire_api` converts the upstream API protocol.
