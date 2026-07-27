# OpenClaw 2026.6 publish compatibility

OpenClaw 2026.6 loads `~/.openclaw/.env` as a runtime dotenv source in addition to `openclaw.json`.

Publisher behavior:

- `.openclaw/openclaw.json` remains the only required OpenClaw packaged config file.
- `.openclaw/agents/main/agent/models.json` is packaged only when it exists.
- `.openclaw/.env` is packaged only when it exists.
- Legacy `_scan_only/.openclaw/agents/main/agent/auth-profiles.json` is optional review context only.
- `_scan_only/.openclaw/.env` is included as review context only when it exists.
- Runtime state and login stores such as `.openclaw/agents/*/agent/openclaw-agent.sqlite`, `.openclaw/credentials`, `.openclaw/devices`, `.openclaw/identity`, and session files are not packaged.

Provider keys referenced from `.openclaw/.env` continue through the existing dotenv materialization, review, and placeholder rewrite path. Unconsumed non-provider secrets in that dotenv file are handled by the generic configuration confirmation path.

When present, `OPENCLAW_CONFIG_PATH` is used as the source for the packaged `.openclaw/openclaw.json`. When present, `OPENCLAW_STATE_DIR` is used as the source root for state files such as `.env`, `agents/main/agent/models.json`, and scan-only main auth profiles. The packaged target paths do not change.

## OpenClaw 2026.6 Provider Compatibility

OpenClaw 2026.6 exposes a broader key-only provider catalog than the original publisher baseline. The publisher selects supported families from the shared official provider registry and applies OpenClaw-specific overrides only where OpenClaw uses a different endpoint, env key, or API format.

Enabled provider groups:

- Baseline: OpenAI, Anthropic, Google.
- Core OpenClaw additions: Z.AI, Moonshot, Kimi Coding, DeepSeek, xAI, OpenRouter.
- Extended key-only catalog: Alibaba/Qwen, MiniMax, NVIDIA, Groq, Mistral, Fireworks, Together AI, Cohere, Novita, StepFun, Tencent TokenHub, Xiaomi, BytePlus, Cerebras, Arcee, GMI, Kilo Code, Qianfan, DeepInfra, Chutes, Venice, Volcengine.

Only providers that can be represented by a supported URL proxy `api_format` and a stable key/base URL pair are enabled.

<details>
<summary>Full enabled provider names</summary>

- `publisher_openai_official`
- `publisher_anthropic_official`
- `publisher_google_official`
- `publisher_arcee_official`
- `publisher_byteplus_official`
- `publisher_byteplus_plan_official`
- `publisher_cerebras_official`
- `publisher_chutes_official`
- `publisher_cohere_official`
- `publisher_deepinfra_official`
- `publisher_zai_official`
- `publisher_moonshot_official`
- `publisher_kimi_official`
- `publisher_deepseek_official`
- `publisher_xai_official`
- `publisher_openrouter_official`
- `publisher_fireworks_official`
- `publisher_gmi_official`
- `publisher_groq_official`
- `publisher_kilocode_official`
- `publisher_minimax_official`
- `publisher_mistral_official`
- `publisher_novita_official`
- `publisher_nvidia_official`
- `publisher_qianfan_official`
- `publisher_qwen_official`
- `publisher_qwen_oauth_official`
- `publisher_stepfun_official`
- `publisher_stepfun_plan_official`
- `publisher_tencent_tokenhub_official`
- `publisher_together_official`
- `publisher_venice_official`
- `publisher_volcengine_official`
- `publisher_volcengine_plan_official`
- `publisher_xiaomi_official`
- `publisher_xiaomi_token_plan_official`

</details>

The publisher recognizes corresponding provider key environment variables from `packaging/_shared/env_profiles/openclaw.json`. Common examples include `CODEX_API_KEY`, `ZAI_API_KEY`, `MOONSHOT_API_KEY`, `KIMI_API_KEY`, `KIMICODE_API_KEY`, `QWEN_API_KEY`, `MODELSTUDIO_API_KEY`, `DASHSCOPE_API_KEY`, `GROQ_API_KEY`, `MINIMAX_API_KEY`, and `VOLCANO_ENGINE_API_KEY`.

For OpenClaw:

- Z.AI defaults to `https://api.z.ai/api/paas/v4` and accepts `ZAI_API_KEY`, with `Z_AI_API_KEY` as an OpenClaw fallback. `ZHIPUAI_API_KEY` is not accepted for OpenClaw.
- Moonshot defaults to `https://api.moonshot.ai/v1` and accepts `MOONSHOT_API_KEY`, with `KIMI_API_KEY` as a fallback.
- Kimi Coding is independent from Moonshot. It uses `anthropic-messages`, defaults to `https://api.kimi.com/coding/`, and accepts `KIMI_API_KEY` or `KIMICODE_API_KEY`.
- DeepSeek defaults to `https://api.deepseek.com`.
- xAI defaults to `https://api.x.ai/v1`.
- OpenRouter defaults to `https://openrouter.ai/api/v1`.

The publisher also scans, prepares, and rewrites providers from the main agent `models.json` at `.openclaw/agents/main/agent/models.json`. In that file, provider fields are rewritten at top-level `providers.<name>.*` paths instead of `models.providers.<name>.*`.

`claude-cli`, `github-copilot`, `ollama-cloud`, OpenCode Zen (`opencode`), OpenCode Go (`opencode-go`), and Nous are intentionally not enabled as OpenClaw official key-only providers in this compatibility pass. They either use login/device-token flows, an API format not currently accepted by the publisher URL proxy contract, a provider catalog that mixes provider-level and model-level API formats, lack a stable manifest-owned base URL/API pair, or are not exposed by the locally installed OpenClaw catalog as a key-only model provider.

Unknown or user-defined OpenClaw providers remain custom provider configuration and continue through the existing base URL / API key confirmation path.
