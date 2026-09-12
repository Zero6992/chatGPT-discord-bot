# Provider contracts and capabilities

Documentation checked **2026-09-08**. The table describes implemented protocol
subsets, not universal compatibility with every provider feature or model. All
listed adapters have offline contract coverage; see the
[support summary](../README.md#supported-backends) for current live coverage.

| Kind | Protocol, authentication and example model | Implemented capabilities |
| --- | --- | --- |
| `openai` | `POST https://api.openai.com/v1/responses`, Bearer key; `gpt-5.6-terra` | Text chat |
| `openai` | `POST /v1/images/generations`, `/v1/images/edits`; `gpt-image-2` | Text-to-image, image-to-image |
| `anthropic` | `POST https://api.anthropic.com/v1/messages`, `x-api-key`, `anthropic-version: 2023-06-01`; `claude-sonnet-5` | Text chat |
| `gemini` | `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`, `x-goog-api-key`; `gemini-3.5-flash` | Text chat |
| `gemini` | `models/veo-3.1-generate-preview:predictLongRunning`, operation GET, authenticated video retrieval | Text-to-video, image-to-video |
| `xai` | `POST https://api.x.ai/v1/responses`, Bearer key; `grok-4.6` | Text chat |
| `xai` | `POST /v1/responses`, `web_search` with `enable_image_search`; `grok-4.6` | Image search, separate alias |
| `xai` | `POST /v1/videos/generations`, `GET /v1/videos/{request_id}`; `grok-imagine-video` | Text-to-video only |
| `deepseek` | `POST https://api.deepseek.com/chat/completions`, Bearer key; `deepseek-v4-flash` | Text chat |
| `compatible` | Administrator base URL + `/chat/completions`; optional Bearer key | Text chat only |
| `codex-cli`, `claude-cli`, `grok-cli` | Unmodified CLI in an isolated runtime; explicit API key or owner's native account/plan login | Text chat only; explicit native sessions |

All modes allow everyone to chat by default; `bot.allowed_user_ids` can optionally
restrict access. Only the configured backend owner can administer CLI account login.
No API fallback or CLI media path is enabled. See [CLI setup and billing](cli.md)
for exact versions, native login commands and runtime requirements. Native
account login and fixed two-turn text/session tests passed for all three CLIs.
The bot's Docker Desktop runner and command callbacks also passed real CLI tests,
including reopening SQLite and resuming the explicit session in a new container.
Local `status` alone checks storage; user-triggered Discord delivery remains a
manual deployment check.

OpenAI uses the [Responses API](https://developers.openai.com/api/docs/guides/text)
and [GPT-5.6 Terra model contract](https://developers.openai.com/api/docs/models/gpt-5.6-terra).
Sol/Terra/Luna API IDs include their version
(`gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`); see the
[family migration guide](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6).
Existing `reasoning.effort=low` and Responses text parameters remain valid.
Billing-related 429 errors are classified using bounded, known error codes and
safe fixed messages. Raw diagnostics are never forwarded and paid requests are
not automatically retried. Unknown/malformed errors retain the generic status
message; see the [official error guide](https://developers.openai.com/api/docs/guides/error-codes).
The separate [Image API](https://developers.openai.com/api/docs/guides/image-generation)
returns base64 image data; editing uses multipart upload. Organization verification
may be required. Image model IDs are independent of chat model IDs.

Anthropic's [Messages API](https://platform.claude.com/docs/en/api/messages/create)
requires `max_tokens`; system instructions are a separate field and response
content is a list of blocks. The adapter concatenates text blocks and excludes
thinking. Example IDs come from the [model overview](https://platform.claude.com/docs/en/models/overview).

Gemini's [generateContent API](https://ai.google.dev/api/generate-content)
receives the full role-translated history once, with `systemInstruction` separately.
It never sends old user turns as separate new generation requests. The example uses
[Gemini 3.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash).
[Veo documentation](https://ai.google.dev/gemini-api/docs/veo) specifies the operation
lifecycle and media retrieval. Image input and generation parameter translations
were also checked against the [official Python SDK converters](https://github.com/googleapis/python-genai/blob/main/google/genai/models.py).

xAI now documents [Responses text generation](https://docs.x.ai/developers/model-capabilities/text/generate-text)
and the [Grok model catalog](https://docs.x.ai/developers/models). Only the compatible
Responses subset implemented here is exposed for chat. The separate
[image-search adapter](https://docs.x.ai/developers/tools/web-search) enables only
`web_search` with `enable_image_search=true`, disables parallel calls and sets
`max_turns` (default 2) and an output token budget. The
[REST schema](https://docs.x.ai/developers/rest-api-reference/inference/responses)
documents `max_turns` on the request; it limits agent turns, not an exact dollar
amount. Failed tools are rejected even when the overall response is `completed`.
Only source-linked public HTTPS image embeds are exposed; no host URL fetch occurs.

The [xAI video adapter](https://docs.x.ai/developers/model-capabilities/video/generation)
validates request UUIDs, polls pending/done/failed/expired states, requires a
moderation-approved artifact and downloads bounded MP4 data only from `vidgen.x.ai`.
The CDN receives no API credential. Only text-to-video is implemented for xAI.
Usage is billed separately from CLI plans; consult xAI's
[cost tracking documentation](https://docs.x.ai/developers/cost-tracking).
DeepSeek documents its own [OpenAI-format contract](https://api-docs.deepseek.com/)
and [Chat Completions fields](https://api-docs.deepseek.com/api/create-chat-completion/).
Neither provider is treated as universally equivalent to OpenAI.

The application uses `httpx.AsyncClient` directly against these official REST
interfaces. Provider SDK installation is unnecessary: this avoids importing old
SDKs, global Gemini SDK configuration, and hidden SDK retries. Official SDKs remain
useful contract references (OpenAI `openai`, Anthropic `anthropic`, Google
`google-genai`, xAI `xai-sdk`); the deprecated Google SDK was removed. HTTP clients
are pooled, bounded, closed on shutdown, and ignore ambient proxy credentials.

## Parameters

Only administrator configuration supplies parameters. No arbitrary per-message
parameter dictionary is accepted.

| Interface | Accepted configuration parameters |
| --- | --- |
| OpenAI/xAI chat | `max_output_tokens`, `reasoning_effort` (`low`, `medium`, `high`) |
| Anthropic chat | `max_output_tokens` (translated to `max_tokens`; default 1024) |
| Gemini chat | `max_output_tokens`, `temperature`, `top_p` |
| DeepSeek chat | `max_output_tokens` → `max_tokens`, `thinking` (`enabled`/`disabled`), `reasoning_effort` |
| Compatible chat | `max_output_tokens` → `max_tokens`, `temperature`, `top_p` |
| CLI text | None; model selection only |
| OpenAI image | `size`, `quality` (validated in configuration) |
| xAI image search | `max_turns` (1–3), `max_output_tokens`; fixed server-side search tool |
| xAI video | `duration_seconds` (1–15), `resolution` (`480p`, `720p`), `aspect_ratio` (`16:9`, `9:16`) |
| Gemini video | `duration_seconds` (4, 6, 8), `aspect_ratio` (`16:9`, `9:16`) |

Model-specific restrictions still apply. If a configured model rejects a parameter,
the adapter reports failure without dropping the parameter or changing models.
Sampling controls are deliberately not exposed for reasoning families that may
ignore or reject them. Truncated text responses fail instead of entering history
as complete assistant turns. Chat, search, image and video need separate aliases.

## Local and custom servers

The adapter intentionally uses the widely supported, stateless text Chat
Completions subset. It does not infer support for Responses sessions, tools,
vision, media or streaming from a server's “OpenAI-compatible” label.

| Server | Base URL example | Setup reference |
| --- | --- | --- |
| Ollama | `http://127.0.0.1:11434/v1` | [Official compatibility documentation](https://docs.ollama.com/api/openai-compatibility) |
| LM Studio | `http://127.0.0.1:1234/v1` | [Official compatible endpoints](https://lmstudio.ai/docs/developer/openai-compat) |
| vLLM | `http://127.0.0.1:8000/v1` | [Official serving documentation](https://docs.vllm.ai/en/stable/serving/online_serving/) |

Run/load a chat-capable model on the server first. Use its installed/served model
ID, including an alias if you configured one. vLLM chat models need a supported
chat template. Server access controls differ; configure `auth = "none"` only when
the server permits unauthenticated access. No placeholder API key is sent.

```toml
[backends.lab]
kind = "compatible"
base_url = "https://inference.example.org/v1"
api_key_env = "LAB_API_KEY"
account = "lab-server-1"

[models.lab]
backend = "lab"
model = "administrator-served-model"
capabilities = ["chat"]
parameters = { max_output_tokens = 2048 }
```

HTTP is allowed only on loopback; use an HTTPS reverse proxy for other hosts.
URLs with embedded credentials, query strings or fragments are rejected. Provider
origins are fixed for official adapters. Discord commands can select configured
aliases but cannot alter URLs, credentials or model IDs.
