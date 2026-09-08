# ChatGPT Discord Bot

[![Offline checks](https://github.com/Zero6992/chatGPT-discord-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Zero6992/chatGPT-discord-bot/actions/workflows/ci.yml)
[![Python 3.12–3.14](https://img.shields.io/badge/python-3.12%E2%80%933.14-blue)](pyproject.toml)
[![License: GPL v2](https://img.shields.io/badge/license-GPL%20v2-blue)](LICENSE)

Bring your favorite AI models into Discord. Chat with OpenAI, Claude, Gemini,
Grok, DeepSeek, or models running on your own machine—all through one bot.

Host it yourself, choose which models your users can access, and keep conversations
across restarts. Each user gets separate history in each server, channel and thread,
with independent private and public conversations.

[Quick start](#quick-start) · [Supported backends](#supported-backends) ·
[Commands](#commands) · [CLI subscriptions](#cli-account-and-subscription-login) ·
[Docker](#docker) · [Migration](docs/migration.md)

## Features

- **Multiple providers:** official APIs and administrator-configured custom endpoints.
- **Local models:** connect Ollama, LM Studio, vLLM or another compatible chat server.
- **Personal CLI access:** use your own eligible Codex, Claude Code or Grok Build
  account through an isolated, owner-only backend.
- **Persistent conversations:** switch models and personas, resume after a restart,
  and reset or delete your history from Discord.
- **Images and video:** generate images, edit attachments, create videos, or search
  for images with explicitly selected API backends.
- **Controlled usage:** configure access, context size, retention and concurrency.
  Provider failures never silently select another model or billing mode.

## Quick start

You need **Python 3.12–3.14**, a Discord bot token, and either an official API key
or a running local model server. Linux, WSL and macOS support API/local backends;
Windows users should use WSL. CLI backends have [additional requirements](docs/cli.md).

### 1. Create and invite your Discord bot

Create an application in the [Discord Developer Portal](https://discord.com/developers/applications)
and obtain its token from the **Bot** page. Keep the token private.

Under **Installation**, enable Guild Install and configure the `bot` and
`applications.commands` scopes. Give the bot **View Channels**, **Send Messages**,
**Embed Links** and **Attach Files** in the channels where you will use it.
For threads, also allow **Send Messages in Threads**. Use the installation link
to add it to your server. Discord's [application setup guide](https://docs.discord.com/developers/quick-start/getting-started)
walks through the portal settings.

Slash commands work without Message Content Intent. Enable it only for
[automatic channel replies](#automatic-channel-replies).

### 2. Install the project

```bash
git clone https://github.com/Zero6992/chatGPT-discord-bot.git
cd chatGPT-discord-bot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
cp config.example.toml config.toml
```

Upgrading an existing installation? Follow the [migration guide](docs/migration.md)
before replacing configuration or dependencies.

### 3. Choose a backend

Credentials go in `.env`; model aliases and access settings go in `config.toml`.
The example includes the backends listed below and defaults to a local server.

**To start with OpenAI**, set these values in `.env`:

```dotenv
DISCORD_BOT_TOKEN=your_discord_bot_token
OPENAI_API_KEY=your_openai_api_key
```

Edit the existing `[bot]` section of `config.toml`:

```toml
[bot]
default_model = "openai"
allowed_user_ids = [123456789] # Replace with your Discord user ID.
```

Keep the other example settings and backend/model sections. The `openai` alias
uses `gpt-5.6-terra`; model IDs are configurable. Enable Discord's Developer Mode
to copy your user ID. An empty `allowed_user_ids` list permits anyone who can
access the bot, so configure access before sharing API usage.

**To start with a local model**, keep `default_model = "local"`, set the model ID
under `[models.local]` to one installed on your server, and choose its base URL:

| Server | Example base URL |
| --- | --- |
| Ollama | `http://127.0.0.1:11434/v1` |
| LM Studio | `http://127.0.0.1:1234/v1` |
| vLLM | `http://127.0.0.1:8000/v1` |

The local example uses `auth = "none"` and needs only the Discord token. For an
authenticated or remote server, see [local/custom configuration](docs/providers.md#local-and-custom-servers).
Remote endpoints require HTTPS; endpoints are controlled by the administrator.

### 4. Start chatting

```bash
python main.py
```

The bot connects to Discord and synchronizes its slash commands. Try:

```text
/chat message:Hello! Help me plan a small Python project.
/models
/provider model:claude
/chat message:Review the plan we just discussed.
/reset
```

Select only backends whose credentials or local service you have configured.
Replies start private. Use `/public` to make future slash replies visible in the
channel, or `/private` to return to your separate private conversation.

## Supported backends

| Backend | Bot capabilities | Credential |
| --- | --- | --- |
| OpenAI | Text chat; image generation and editing | `OPENAI_API_KEY` |
| Anthropic | Claude text chat | `ANTHROPIC_API_KEY` |
| Google Gemini | Text chat; Veo text-to-video and image-to-video | `GEMINI_API_KEY` |
| xAI Grok | Text chat; image search; text-to-video | `XAI_API_KEY` |
| DeepSeek | Text chat | `DEEPSEEK_API_KEY` |
| Local/custom servers | Compatible text Chat Completions | Optional administrator-configured key |
| Codex, Claude Code, Grok Build CLI | Isolated text conversations and explicit session resumption | API key or native account login; owner-only |

Configure model IDs, aliases and supported parameters in TOML. New model aliases
do not require Python changes. Each alias declares its capabilities; chat, search
and media use separate aliases. Unsupported settings fail explicitly.
Configuration changes require restarting the bot.

Text chat accepts text only. Vision, audio, streaming and general agent tools are
not exposed. Long replies arrive as a text attachment to preserve formatting.

Adapters have offline contract coverage, with live checks for OpenAI/Anthropic/xAI
chat, native CLI account text and xAI video. Other paths have outstanding live
verification or provider errors. See the [capability reference](docs/providers.md)
and the CLI and media limitations below before enabling a backend.

## Commands

| Command | What it does |
| --- | --- |
| `/chat message` | Send a message in your current conversation |
| `/models` | List configured models, capabilities and authentication modes |
| `/provider model` | Change the chat model for your conversation |
| `/private`, `/public` | Choose the audience and its separate history |
| `/switchpersona persona` | Change the conversation's personality |
| `/reset` | Clear the current history, native session state and media job mappings |
| `/delete` | Clear both your private and public histories in this channel |
| `/image_search query model` | Find images and show up to three source-linked previews |
| `/draw prompt model [image]` | Generate an image or edit an attached PNG/JPEG |
| `/video prompt model [image]` | Generate a video; image input requires a Veo alias |
| `/job job_id` | Retrieve an existing video job without another generation request |
| `/cancel` | Cancel outstanding requests in your current conversation |
| `/cli_auth action model` | Owner-only CLI login, status, logout or cancellation; always private |
| `/replyall enabled` | Administrator control for automatic channel replies |
| `/help` | Show the command reference |

Personas include `standard`, `creative`, `technical` and `casual`. Restricted
personas require an ID listed in `bot.admin_user_ids`.

### Automatic channel replies

Add channel IDs to `bot.reply_channels`, set `bot.admin_user_ids`, enable
[Message Content Intent](https://docs.discord.com/developers/events/gateway#message-content-intent)
in the Developer Portal, and restart. The bot replies to ordinary user messages in
those channels. An administrator can use `/replyall enabled:false` to pause it.

Automatic replies are public and use the author's public history. Other bots and
webhooks are ignored. Leave `reply_channels = []` for slash commands only.

## Conversation history

History is stored in SQLite at `data/conversations.sqlite3` by default. Conversations
are scoped to the bot account, server or DM, channel or thread, requesting user,
and private/public audience. Other users do not contribute to your model context;
public replies are still visible to people in that channel.

Defaults retain **100 completed turns** and expire conversations after **30 days
of inactivity**. Adjust `max_turns`, `retention_days` and `context_bytes` in `[bot]`.
The context budget counts UTF-8 bytes conservatively, not exact tokens. Requests
in one conversation run in order, with bounded concurrency between conversations.

Switching model, provider or persona preserves retained text and reconstructs
context when native session reuse is inappropriate. Failed or cancelled generation
does not add a turn. `/reset` restores the default model and persona, while keeping
CLI login. Use `/cli_auth action:logout model:ALIAS` to sign out.

Keep the database on persistent disk and run one bot process per database. Stop
the bot before copying it, or use SQLite's backup API. Protect backups as private
conversation data. Deleting bot history does not delete messages already sent to
Discord or data retained by a provider. See [storage and migration](docs/migration.md).

## CLI account and subscription login

Use your own eligible Codex, Claude Code or Grok Build account for a **personal bot**.
Account mode requires `allowed_user_ids` to contain only the account owner; shared
subscription access is disabled. Use official API backends for shared services.

Start with [config.account.example.toml](config.account.example.toml) and follow the
[CLI setup guide](docs/cli.md) to provision pinned images, a dedicated rootless
Docker daemon, systemd/cgroup v2 resource controls, seccomp and restricted egress.
The bot refuses CLI execution when required isolation is unavailable.

Once the runtime is ready, the owner can initiate Codex or Grok device login:

```text
/cli_auth action:login model:codex_account
/cli_auth action:login model:grok_account
/cli_auth action:status model:codex_account
```

The private response contains the native CLI's official authorization URL and
device code. Complete login on the provider website. Claude login uses a private
local terminal:

```bash
python -m src.cli_accounts login claude_account --config config.toml
```

All three CLIs support local `login`, `status` and `logout` administration.
Credentials stay in dedicated runtime storage; no OAuth token belongs in `.env`
or a Discord message. Re-login preserves bot history and invalidates old sessions.

`auth = "account"` uses applicable plan allowances and any enabled extra usage.
`auth = "api"` is billed separately to the API key owner. Subscriptions do not imply
unlimited automation or media access. CLI image/video generation and image search
are not implemented. See [provider-specific restrictions](docs/cli.md#authentication-and-deployment).
Native account text/session checks have passed; the persistent bot runtime's
incoming Discord command flow still needs live verification.

## Images, video and image search

The main example includes optional media aliases. Configure the corresponding
API key, then select an alias explicitly:

```text
/draw prompt:A watercolor fox reading a book model:image
/video prompt:An orange ball rolling on a white table model:xai_video
/image_search query:Taipei 101 at sunset model:image_search
```

Attach a PNG/JPEG to `/draw` to edit it. The OpenAI image example requests low
quality at 1024×1024. The xAI video example requests one second at 480p; the `video`
alias uses Gemini Veo and also accepts image input. API charges apply separately
from CLI subscriptions.

Video jobs show an ID while processing. `/job` resumes retrieval after a restart,
without another generation POST. `/cancel` stops local waiting; submitted remote
jobs may continue and be billed. Submission timeouts are not automatically retried.

Generated files are attached to Discord, subject to the configured **8 MiB** default
and the server's upload limit. Administrators may raise the bot cap up to 25 MiB.
Artifacts are not archived locally; interrupted image delivery cannot be recovered
with `/job`. Search previews use Discord's image proxy, and source sites may block them.

Media adapters have offline contract tests. Live artifact generation and delivery
have been verified for xAI video; image generation/search and Veo have outstanding
provider checks. Confirm model access, account limits and artifact delivery with
your selected provider before enabling paid operations for other users.

## Docker

After configuring `.env` and `config.toml`, create persistent storage and allow
container UID 1001 to write to it. For a **new** data directory on Linux:

```bash
sudo install -d -m 700 -o 1001 -g 1001 data
docker compose up -d --build
docker compose logs -f bot
```

For existing data, back it up and review ownership before changing permissions.
The application runs as a non-root user with a read-only application filesystem.
Compose supports API and local/custom HTTP backends; it has no Docker socket and
cannot run nested CLI backends.

Container `127.0.0.1` refers to that container. To use a model server on another
host, configure a reachable administrator-controlled HTTPS endpoint. Run the bot
directly on the host when using the documented CLI runtime.

## Upgrading

Version 4 changes configuration and conversation storage. Unofficial free-provider
aggregators, browser-cookie authentication and hidden fallbacks have been removed.
Use an official API, a local/custom endpoint or a supported personal CLI backend.
Legitimate official API free tiers remain supported.

Follow the [migration guide](docs/migration.md) for environment-variable mappings,
persona migration, database handling and rollback. Preserve existing configuration
and user files before upgrading.

## Development and contributing

Bug reports and pull requests are welcome. Include reproduction steps, runtime
versions and the affected model alias; remove tokens and private conversation data.
The [architecture guide](docs/architecture.md) explains the provider, conversation,
CLI and Discord boundaries.

Install Node.js **22+** for account-runtime tests, then run:

```bash
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
python -m pytest
ruff check .
ruff format --check .
mypy
python -m build
python -m pip check
pip-audit -r requirements.txt
```

The default suite is deterministic and offline, using HTTP fixtures, temporary
SQLite databases and fake CLI executables. CI runs Python 3.12–3.14 with Node.js 24.
Paid smoke tests require explicit opt-in and credentials. They read process
environment variables, not `.env` automatically. To deliberately test one chat alias:

```bash
BOT_LIVE_TESTS=1 BOT_ALLOW_PAID_TESTS=1 LIVE_CHAT_MODEL=openai \
  python -m pytest -m live -k chat -q
```

Use `LIVE_IMAGE_MODEL`, `LIVE_VIDEO_MODEL` or `LIVE_CLI_MODEL` and the corresponding
`-k` filter for other operations. CLI tests require the configured isolated runtime
and completed login. Missing opt-in, credentials or model selectors are reported
as skipped. API credits, plan allowances or enabled extra usage may be consumed.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Slash commands do not appear | Confirm the bot is running, the installation has `applications.commands`, and startup synchronization succeeded |
| Missing credential or unavailable model | Check the selected alias, its `api_key_env`, the model ID and provider access |
| HTTP 429 | Check provider billing, quota and rate limits before trying again |
| Old configuration rejected | Apply the [migration guide](docs/migration.md); outdated fields are intentionally rejected |
| Local endpoint unreachable in Docker | Use a reachable HTTPS endpoint; container loopback is not the host |
| CLI runtime unavailable | Check the pinned version, rootless daemon, resource controls, seccomp and proxy using the [runtime guide](docs/cli.md) |
| Generated attachment too large | Request a shorter/smaller artifact or adjust the cap within Discord's limit |

## License

[GNU General Public License v2.0](LICENSE).
