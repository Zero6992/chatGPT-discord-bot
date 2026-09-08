# Migration from the legacy bot

This configuration-breaking modernization uses package version **4.0.0**. The
existing `v3.0.0` Git tag identifies the legacy code and is preserved; a branch
push does not create a new release or move an existing tag.

Stop the old bot and preserve `.env`, custom prompts and any user-maintained
files. The old implementation held a single shared history in memory; it had no
safe per-user durable database to import. Do not assign that shared history or
arbitrary “latest” native sessions to a user. The new database starts empty.

1. Create a Python 3.12–3.14 virtual environment and install the new requirements.
   Do not reuse the old dependency environment. Browser automation, cookie login,
   unofficial endpoint aggregators and their hidden fallbacks have been removed.
2. Copy `config.example.toml` to `config.toml`, and create `.env` using the example.
   Keep `DISCORD_BOT_TOKEN`. Convert API variables using the table below. Set the
   default model alias explicitly; the example uses a local server.
3. Configure allowed/admin user IDs and channels in TOML. Use a real local model
   ID or your official API's current ID. Copy useful `system_prompt.txt` text into
   `bot.system_prompt`; it is now an instruction, not a paid startup conversation.
   The original prompt file and untracked user files are not deleted.
4. Remove outdated settings from the active `.env`. Preserve any archive privately.
   Startup rejects obsolete settings instead of silently changing backend or
   billing behavior. Consumer-site cookies and shared free credentials cannot be
   configured as integrations. Official native CLI account login is a separate
   explicit mode described below.
5. Start the bot once; it synchronizes the current slash commands. Test two users,
   two channels, private/public mode, a restart and a reset before wider use.

| Previous configuration | New configuration |
| --- | --- |
| `OPENAI_KEY` | `OPENAI_API_KEY` or another variable referenced by `api_key_env` |
| `CLAUDE_KEY` | `ANTHROPIC_API_KEY` |
| `GEMINI_KEY` | `GEMINI_API_KEY` |
| `GROK_KEY` | `XAI_API_KEY` |
| `DEFAULT_PROVIDER`, `DEFAULT_MODEL`, `MODEL` | TOML backend/model aliases and `bot.default_model` |
| `ADMIN_USER_IDS` | `bot.admin_user_ids = [123, 456]` |
| `MAX_CONVERSATION_LENGTH`, `CONVERSATION_TRIM_SIZE` | `max_turns`, `context_bytes`, `retention_days` |
| `REPLYING_ALL`, `REPLYING_ALL_DISCORD_CHANNEL_ID` | `bot.reply_channels` plus admin `/replyall enabled` |
| `DISCORD_CHANNEL_ID` startup response | No automatic startup inference/message |
| `LOGGING` | Safe operational logging always enabled; no prompt logs |
| `OPENAI_ENABLED`, `OPENAI_TEMPERTUARES` | Explicit alias and supported parameters |
| `BING_COOKIE`, `GOOGLE_PSID`, `G4F_*`, `free`/`g4f` provider kind | Removed; choose an official API or administrator-hosted compatible server |

Changes users should expect:

- Private and public histories are separate, and default slash replies are private.
  Provider/persona/reset actions affect only the user's current context.
- Long responses arrive as text files rather than many public follow-up messages.
- Provider/persona changes preserve bot text history and rebuild native context.
- `/draw` and `/video` require a media alias; an unavailable media provider cannot
  trigger another paid service. Existing unsupported media code was removed.
- Official APIs with legitimate free tiers remain supported through API keys and
  the same explicit billing/account choices.

Schema version 1 is newly introduced. Existing unknown schemas are rejected before
schema creation; do not overwrite a database to make startup succeed. Store data
in a private directory owned by the bot, and mount it persistently in Docker.
Use SQLite backup or stop the bot before copying SQLite/WAL files. Never run two
processes against the same database. Rollback means stopping the new bot and using
the old code/config in a separate environment; do not interpret a new database as
legacy data.

## Opt into native CLI account login

Existing API/local configurations and schema version 1 remain valid. To enable
subscription/account mode, merge the needed blocks from
[config.account.example.toml](../config.account.example.toml) and follow
[CLI provisioning and login](cli.md). Restrict the entire bot to the account owner,
rebuild pinned CLI images with the account helper, and configure the account proxy.
Use a fresh private `auth_profile` metadata directory for each backend. Do not
import an existing personal CLI credential cache or overwrite the database.

Remove `api_key_env` from account backends; they reject mixed authentication.
Keep separately configured API/media keys where needed. Native browser/device
login replaces token environment variables for account mode. Switching modes or
re-logging in preserves bot history and reconstructs native context. `/reset` and
retention keep account login; `/cli_auth action:logout model:ALIAS` or local
`cli-auth logout ALIAS` signs out. Codex/Grok device login can now be initiated
through the always-private `/cli_auth` command; Claude login remains in the local
terminal. No additional OAuth token environment variable or database migration is
needed. Shared subscription bots remain unsupported; CLI media is not exposed
by this bot (see [native capability boundaries](cli.md#media-and-image-search-boundaries)).

## Image search and xAI video aliases

No schema migration or credential replacement is needed. Merge the optional
`models.image_search` and `models.xai_video` blocks from the main example, pointing
them at your configured xAI API backend. Restart to register `/image_search`; use
`/video model:xai_video` explicitly for xAI video. Existing OpenAI image and Veo
aliases remain valid. This adds no automatic fallback or recurring paid tests.
