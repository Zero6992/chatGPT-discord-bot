# Isolated CLI backends

Claude Code, Codex and official Grok Build support text conversations through their
unmodified native CLIs. Choose `auth = "api"` for a dedicated API key or
`auth = "account"` for the owner's native account/subscription login. Both require
explicit configuration. This bot currently exposes CLI text only. Its media/search
paths require separate capability, billing and artifact verification described below.

## Authentication and deployment

All modes allow everyone to chat by default, including CLI API-key and account
login on rootless Docker or Docker Desktop. Leave `bot.allowed_user_ids = []` or
omit it. Set a nonempty list only when you want to restrict chat to those users.
Each backend's `owner_id` controls account login, status, logout and cancellation;
the owner must also be allowed by any configured user list. Conversation history
and native sessions stay separate for each user. Provider account and plan terms
still apply independently of the bot's chat permissions.

| Mode | Login | Usage and billing |
| --- | --- | --- |
| `api` | Administrator-configured `api_key_env` | Billed to that API account; chat subscriptions do not cover these API calls |
| `account` | Native browser/device flow through local `cli-auth login MODEL`; Codex/Grok also support private `/cli_auth` instructions | Requires eligible CLI access; uses applicable plan allowances or enabled extra usage |

Account login does not promise unlimited usage, API credits, every model, or media
generation. Non-interactive allowances can differ from interactive usage. Check the
provider's current plan and usage settings. The bot never switches authentication
mode or submits through an API key after an account-authentication or quota failure.

Documented boundaries checked 2026-09-08:

- **Codex:** [native authentication](https://learn.chatgpt.com/docs/auth) distinguishes
  ChatGPT login from API keys. OpenAI documents account auth for
  [trusted private automation](https://learn.chatgpt.com/docs/auth/ci-cd-auth), with
  serialized native refresh and persistence of the updated cache. Use one machine
  and one serialized account execution stream. Do not reuse this login in public
  CI, other machines, or your ordinary interactive CLI profile.
- **Claude Code:** the current English
  [deployment rules](https://code.claude.com/docs/en/legal-and-compliance) permit an
  end user to sign in to the unmodified binary with their own subscription. They
  prohibit third-party Claude.ai login implementations and credential pooling.
  Here, the owner completes Anthropic's native flow in a private local terminal.
  Discord has no login form, token input or OAuth API. Account credentials stay in
  the backend's dedicated runtime storage; chat access uses `allowed_user_ids`.
- **Grok Build:** [official documentation](https://docs.x.ai/build/overview) describes
  native account sign-in and headless integrations. The official
  [authentication guide](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/02-authentication.md)
  documents device login, storage and refresh. xAI controls account/plan eligibility.

## Provision the runtime

The bot runs coding agents inside containers. Choose a daemon explicitly in each
CLI backend. The default Compose service has no Docker socket; run the CLI-enabled
bot as a Linux/WSL host process with access to the selected daemon. The socket
is never mounted into an inference container.

| `docker_mode` | Runtime requirements |
| --- | --- |
| `rootless` (default) | Dedicated rootless daemon, active seccomp, systemd and cgroup v2; socket such as `/run/user/1000/docker.sock` |
| `desktop` | Docker Desktop Linux daemon, cgroup v2, explicit hash-pinned seccomp profile, and successful in-container isolation probes |

### Rootless setup

Rootless alone does not establish resource isolation. Preflight also requires
`CgroupDriver=systemd`, `CgroupVersion=2` and true `MemoryLimit`, `CpuCfsQuota` and
`PidsLimit` flags. Docker can otherwise silently ignore the configured limits;
see its [rootless resource requirements](https://docs.docker.com/engine/security/rootless/tips/#limiting-resources).
The bot refuses login and inference when any required limit is unavailable.

For WSL, install `uidmap`, `slirp4netns`, `systemd-sysv` and `dbus-user-session`.
Enable systemd by merging the following into `/etc/wsl.conf`, preserving any
other settings:

```ini
[boot]
systemd=true
```

CPU, memory and PID controllers must be delegated to the daemon's user. In a new
drop-in such as `/etc/systemd/system/user@1000.service.d/chatgptbot-delegate.conf`
(replace 1000 with the daemon user's UID), configure:

```ini
[Service]
Delegate=cpu memory pids
```

Save active work, then restart WSL from Windows; this interrupts processes in
the distribution. Microsoft documents the
[WSL systemd setup and restart](https://learn.microsoft.com/en-us/windows/wsl/systemd).
After reopening WSL, confirm systemd is PID 1 and start/provision the rootless
daemon. A non-systemd daemon or installing the UID helper packages alone does
not satisfy rootless mode's runtime requirements. Set `DOCKER_HOST` to the
selected socket for the build and network commands below:

```bash
export DOCKER_HOST=unix:///run/user/1000/docker.sock
```

### Docker Desktop setup

An already running [Docker Desktop WSL backend](https://docs.docker.com/desktop/features/wsl/)
can be used without changing the distribution's init system. Chat access follows
`allowed_user_ids`, with everyone allowed by default.
Access to the selected Docker daemon remains an administrator privilege.

Obtain and review Docker's [default seccomp profile](https://docs.docker.com/engine/security/seccomp/#pass-a-profile-for-a-container),
save the JSON on the bot host, and calculate its hash with
`sha256sum /absolute/path/to/seccomp.json`. Configure each CLI backend explicitly:

```toml
docker_mode = "desktop"
docker_socket = "/var/run/docker.sock"
seccomp_profile = "/absolute/path/to/seccomp.json"
seccomp_sha256 = "REPLACE_WITH_THE_64_HEX_SHA256"
```

The bot requires a matching hash and `defaultAction = "SCMP_ACT_ERRNO"`, supplies
the profile to every container, and rejects profile changes before execution.
Preflight verifies Docker Desktop identification, effective seccomp and
no-new-privileges, UID 65532, no capabilities, a read-only root, the owned account
directory, and CPU/memory/PID limits read from inside the container. It accepts
Desktop's cgroupfs driver with cgroup v2. Each inference container is limited to
one CPU, 1 GiB of memory, no extra swap and 128 PIDs. Container log storage is
disabled; only the bounded application subprocess pipes receive CLI output.

Use Docker's Unix socket for the following setup commands:

```bash
export DOCKER_HOST=unix:///var/run/docker.sock
```

### Images and restricted network

Build one image per CLI with `runtime/Dockerfile.cli`. Account mode requires its
fixed helper and `io.chatgptbot.account-auth=1` label; older images are rejected.
Images must contain no credentials, repository, host profile or implicit volumes.
Pin each immutable image ID in configuration, not a mutable tag.
The Grok image materializes its compressed executable with the official installer
at build time, avoiding executable installation in conversation storage. Every
image must pass a version check under its non-root user during the build.

```bash
docker info --format '{{json .SecurityOptions}}'
docker info --format '{{.CgroupDriver}} {{.CgroupVersion}} memory={{.MemoryLimit}} cpu={{.CpuCfsQuota}} pids={{.PidsLimit}}'
docker build -f runtime/Dockerfile.cli --build-arg CLI_KIND=codex-cli \
  --build-arg CLI_VERSION=0.153.4 -t bot-codex:0.153.4 runtime
docker image inspect bot-codex:0.153.4 --format '{{.Id}}'
```

For the other images use `CLI_KIND=claude-cli`, `CLI_VERSION=2.1.263`, or
`CLI_KIND=grok-cli`, `CLI_VERSION=1.0.13`. Use the same Linux user and configuration
path for login and inference.

Containers use an **internal Docker network**. A separately administered CONNECT
proxy is its only connection to external networks. Account login needs the exact
auth/inference origins in `runtime/squid-account.conf`; `runtime/squid.conf` remains
the API configuration. Select the account proxy explicitly:

```bash
docker build -f runtime/Dockerfile.proxy --build-arg PROXY_CONFIG=squid-account.conf \
  -t bot-account-proxy:local runtime
docker network create --internal bot-account-internal
docker network create bot-account-egress
docker run -d --name bot-account-egress --network bot-account-egress --read-only \
  --tmpfs /tmp:rw,nosuid,size=32m --cap-drop ALL \
  --security-opt no-new-privileges bot-account-proxy:local
docker network connect --alias egress bot-account-internal bot-account-egress
```

These are local provisioning instructions, not actions performed automatically.
Review the proxy ACL and trim it to your selected providers. API and account
backends may use separate proxy networks. The ACL allows CONNECT to HTTPS port
443 only and disables request logs. Codex account traffic uses ChatGPT/auth
origins; Grok uses its CLI proxy/auth origins. See Claude's
[network configuration](https://code.claude.com/docs/en/network-config) and Grok's
[enterprise guide](https://docs.x.ai/build/enterprise).

## Configure and sign in

Start from [config.account.example.toml](../config.account.example.toml), or merge
its selected backend/model blocks into your existing configuration. Replace the
owner/user IDs, socket UID, image digests and model IDs; remove unused backends.
Do not overwrite an existing config or database. The key account fields are:

```toml
# Inside the chosen [backends.NAME] block:
auth = "account"
owner_id = 123456789
account = "personal-codex"
auth_profile = "data/cli-auth/codex"
# Omit api_key_env and base_url; configure image, version, socket and proxy.
```

`auth_profile` is a new private directory for bot metadata and a lock, **not** a
native credential path. Relative paths resolve beside the TOML file. Use a
different profile per backend. Directory permissions must enforce mode 0700:
on WSL, use the Linux filesystem if the Windows drive cannot enforce it.
Credentials stay in a dedicated account Docker volume. Do not copy host
`auth.json`, `.credentials.json`, browser cookies or tokens into this directory.

### Discord device login (Codex and Grok)

After provisioning the runtime and starting the bot, its configured owner can use:

```text
/cli_auth action:login model:codex_account
/cli_auth action:login model:grok_account
/cli_auth action:status model:codex_account
/cli_auth action:cancel model:codex_account
/cli_auth action:logout model:codex_account
```

Login starts the unchanged CLI's `login --device-auth` workflow. The response is
always private, regardless of the current conversation's audience. Open the
official URL and confirm/enter the displayed device code **on that website** for
the login you just requested. The native CLI handles polling and credential
storage. The bot never accepts a pasted token or code and has no OAuth callback
or custom token-exchange implementation. Codex device login may require enabling
the option in your account/workspace's security settings; see its
[authentication documentation](https://learn.chatgpt.com/docs/auth).

Only the expected native prompt's URL/code are extracted from bounded output;
arbitrary CLI diagnostics are not forwarded. URLs require the exact official
HTTPS origin, approved path/query shape, and a matching device code. The prompt
parser is pinned to the verified CLI versions and fails closed if the native
format changes. Grok's live device service also returns
`https://accounts.x.ai/oauth2/device`; that exact destination and the documented
`auth.x.ai` device paths are accepted, with only an optional matching `user_code`.
The account proxy includes both official hosts. Login has a ten-minute deadline, including runtime checks. On
success, failure or cancellation the bot replaces its private challenge message.
If Discord delivery fails, login is cancelled and containers are cleaned up.

Aliases sharing an account cannot start duplicate login jobs. Account operations
are bounded to the smaller of configured concurrency and four; `status` reports
pending work and `cancel` waits for cleanup. Bot shutdown cancels pending login.
The account lease also serializes authentication against conversation execution.
Runtime verification must pass before a real login URL can be produced.

Claude Code's current native flow requires its browser callback or pasting an
authorization code into the local terminal. This integration does **not** relay
that flow through Discord; `/cli_auth login` gives the local command instead.
Its `status` and `logout` operations are supported through Discord. This is an
implementation limitation, not a claim that every hosted native login is forbidden.

### Private local terminal (all three CLIs)

Install the project, then run these commands in a private interactive terminal
for the aliases you configured:

```bash
python -m pip install --no-deps -e .
cli-auth login codex_account --config config.toml
cli-auth login claude_account --config config.toml
cli-auth login grok_account --config config.toml
cli-auth status codex_account --config config.toml
cli-auth logout codex_account --config config.toml
```

`python -m src.cli_accounts` is equivalent to `cli-auth`. Codex and Grok display
native device authorization instructions. Claude displays its official login URL;
open it in your browser and paste the authorization code, if requested, into that
**local CLI terminal**. Its documented
[container/WSL fallback](https://code.claude.com/docs/en/troubleshoot-install#oauth-login-fails-in-wsl2-ssh-or-containers)
needs no exposed callback port. Login has a ten-minute total deadline.
Do not paste authorization codes into Discord or a chat with the assistant.

### Native login checks without restarting WSL

The systemd/cgroup requirement above belongs to this bot's isolated execution
runtime and `/cli_auth` integration. Official native CLI login can be checked
separately without restarting WSL or starting an agent/model task.

Use a fresh private provider profile and the installed unmodified CLI's login
command; preserve profiles used by existing sessions. Codex documents
[`codex login --device-auth`](https://learn.chatgpt.com/docs/auth#login-on-headless-devices).
Grok supports the same separate check using `grok login --device-auth`.
Only validated native device URLs/codes may be sent privately to the owner. Keep API
keys out of that login process and never forward credentials or raw diagnostics.
This checks account login only: it does not enable the bot's runtime, verify model
entitlement, import a profile into the bot, or permit host execution of Discord
prompts.

Defer WSL restarts while other work is active. `wsl --shutdown` stops all
distributions; `wsl --terminate NAME` still stops every session in that named
distribution, so it does not preserve other sessions in the same Ubuntu instance.
See [Microsoft's command definitions](https://learn.microsoft.com/en-us/windows/wsl/basic-commands#shutdown).

No OAuth environment variable is needed. Account backend configuration rejects
`api_key_env` and custom `base_url`. Keep `DISCORD_BOT_TOKEN` in `.env` for the bot;
API keys are needed only for separately selected API/media aliases. `/models`
and `/provider` display the configured billing mode.

`status` checks local credential presence and configuration, not remote validity
or subscription eligibility; its JSON sets `provider_verified: false`. A failed
or cancelled login disables the profile until login succeeds again. Logout
invalidates native mappings and invokes native logout; it does not promise
provider-wide revocation on other devices.

For API mode, keep `auth = "api"`, an owner-specific `api_key_env`, and omit
`auth_profile`. Each CLI backend remains restricted to its configured owner.

## Native execution contracts

| CLI/version | Account login command | Text and session contract |
| --- | --- | --- |
| Codex `0.153.4` | `codex login --device-auth`, forced ChatGPT mode and file storage | `codex exec --json … -`; explicit `exec resume UUID`; forced `chatgpt` or `api` auth |
| Claude Code `2.1.263` | `claude auth login --claudeai` | `--print --output-format json`; explicit `--resume UUID`; `--safe-mode` for account, `--bare` for API |
| Official Grok `1.0.13` | `grok login --device-auth` | `--prompt-file /dev/stdin --output-format streaming-messages-json`; explicit `--resume UUID` |

Claude bare mode omits subscription login, so account mode uses safe mode to keep
auth while disabling customizations. Both disable tools, MCP servers, skills and
slash commands. Codex disables shell execution, unified exec, apps, agents, web
search and ambient rules/configuration with a read-only sandbox. Grok uses empty
tools plus `--deny "*"`, no subagents and no web search. No latest-session shortcut
is used. Structured results, terminal success and UUIDs are validated; unexpected
tool results are rejected. See the official
[Claude programmatic interface](https://code.claude.com/docs/en/headless),
[Codex exec documentation](https://developers.openai.com/codex/noninteractive), and
[Grok headless guide](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/14-headless-mode.md).

## Credentials, context and cleanup

Containers use UID 65532, a read-only filesystem and empty `/work`, no capabilities
or added privileges, bounded CPU/memory/PIDs, and small `noexec` temporary storage.
No host path or repository is mounted. A fixed helper copies only allowlisted
native credential files between the account and conversation volumes **inside
Docker**. It runs the unmodified CLI, saves refreshed credentials, then removes
the conversation copy. Python never parses OAuth tokens. No custom token exchange
is used, and transcripts never return to the account volume.

An account lease serializes login/logout and all aliases/conversations using that
profile, including the history commit. Native refresh keeps the profile revision;
login/logout rotates it before changing credentials. SQLite history survives
restart and re-login while old native mappings become invalid. Changing provider,
model, account or persona reconstructs retained text once. Uncertain execution
invalidates its mapping before another request; no automatic paid retry occurs.

Reset/delete and retention remove history and bot-labeled transcript volumes.
They preserve account login; use `/cli_auth action:logout model:ALIAS` or
`cli-auth logout ALIAS` to sign out. Protect the account
volume as credentials and SQLite as private history. Avoid concurrent copies of
the native login on other machines. This is separate from your personal CLI profile.

Subprocesses use argument arrays, bounded pipes, stdin and total deadlines.
Cancellation stops the container gracefully to save refreshed credentials, then
forces removal if needed. A daemon crash or forced kill can interrupt the flush
and require re-login. Stale conversation credentials never replace the current
account login on the next run. Raw diagnostics and session IDs stay out of Discord
and ordinary logs.

Codex chat explicitly disables its native image generation/viewer, browser/computer
tools, code-mode host, plugins, hooks, skill discovery, background goals and
unbounded connection retries, in addition to the shell/agent/app restrictions.
The installed 0.153.4 binary was probed without networking or credentials: the
image/tool controls report false. Its `unified_exec` display remains true despite
the compatibility override; `shell_tool=false` is the master shell gate.
Codex 0.153.4 emits an `item.completed` error-shaped notice when Code Mode is
intentionally disabled. The parser accepts only that exact known notice; other
runtime errors, failed turns and tool events still fail closed. A restricted
manual account test passed both text and explicit session resumption.

Offline tests exercise the real credential helper with fake native executables.
Native account login and two-turn text/session checks passed for all three CLIs.
Actual expired-token refresh, persistent bot-runtime integration and
owner-triggered Discord commands still need live verification;
local status and version/help alone do not establish authenticated behavior.

## Media and image-search boundaries

These are **bot adapter limits**, not a claim that every native CLI lacks media:

| Native product | Verified documentation | Bot status |
| --- | --- | --- |
| Codex | Built-in image generation uses `gpt-image-2` and plan usage; interactive CLI is documented | Disabled: no implemented and verified `exec` artifact contract; account login and text checks passed |
| Grok Build | TUI `/imagine` and `/imagine-video`; video tools and ZDR output-storage requirements | Disabled: headless media output, minimum-quality controls and this account's subscription entitlement unverified |
| Claude Code | WebSearch returns titles/URLs; no native image/video generation contract verified | Media disabled; WebSearch is not enabled by this bot |

Sources: [Codex images](https://learn.chatgpt.com/docs/image-generation),
[Grok commands](https://docs.x.ai/build/modes-and-commands),
[Grok headless mode](https://docs.x.ai/build/cli/headless-scripting),
[Grok video storage](https://docs.x.ai/build/settings/zdr-video-storage), and
[Claude tools](https://code.claude.com/docs/en/tools-reference). Checked 2026-09-08.
Interactive commands and generic headless support do not establish an exact
programmatic media contract. Grok video under ZDR requires administrator-supplied
storage; do not silently change privacy settings to enable it.

Both configured runtime modes require effective resource controls. Rootless mode
requires systemd; explicit Docker Desktop mode uses its own verified Linux daemon.
Native account login and isolated manual text checks have passed.
Before exposing CLI media, verify the approved account's actual tools,
headless structured artifact output, provider billing and narrowly allowed tool
execution before enabling any CLI media alias. No shell/API-key wrapper is called
subscription-backed generation. The one-time successful video test used the xAI
API key, not a CLI subscription. API image/search errors are never retried via CLI.
