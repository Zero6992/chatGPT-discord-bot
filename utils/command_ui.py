"""Discord presentation for configured models and command help."""

import discord
from discord import app_commands

from src.config import CLI_KINDS, Model, Settings
from src.domain import Capability

BACKEND_LABELS = {
    "openai": "OpenAI API",
    "anthropic": "Anthropic API",
    "xai": "xAI API",
    "gemini": "Google Gemini API",
    "deepseek": "DeepSeek API",
    "compatible": "Local / custom API",
    "claude-cli": "Claude Code",
    "codex-cli": "Codex CLI",
    "grok-cli": "Grok CLI",
}
CAPABILITY_LABELS = {
    Capability.CHAT: "Chat",
    Capability.IMAGE_SEARCH: "Image search",
    Capability.TEXT_TO_IMAGE: "Create images",
    Capability.IMAGE_TO_IMAGE: "Edit images",
    Capability.TEXT_TO_VIDEO: "Create videos",
    Capability.IMAGE_TO_VIDEO: "Animate images",
}
COLOUR = 0x5865F2


def visible_models(settings: Settings, user_id: int) -> list[Model]:
    if settings.allowed_user_ids and user_id not in settings.allowed_user_ids:
        return []
    return list(settings.models.values())


def model_choices(
    settings: Settings, user_id: int, capability: Capability, current: str
) -> list[app_commands.Choice[str]]:
    choices = []
    for model in visible_models(settings, user_id):
        label = f"{model.name} · {BACKEND_LABELS[model.backend.kind]} · {model.model}"
        if capability in model.capabilities and current.casefold() in label.casefold():
            choices.append(app_commands.Choice(name=label[:100], value=model.name))
            if len(choices) == 25:
                break
    return choices


def _inline_code(value: str) -> str:
    return "`" + value.replace("`", "'").replace("\n", " ")[:600] + "`"


def model_pages(models: list[Model], selected: str) -> list[discord.Embed]:
    description = (
        "Choose a chat model with **/provider**. Image, video and search commands "
        "have their own model menus.\n"
        f"**Current chat alias:** {_inline_code(selected)}"
    )
    pages = []

    def new_page() -> discord.Embed:
        page = discord.Embed(title="Available models", description=description, colour=COLOUR)
        pages.append(page)
        return page

    page = new_page()
    for model in models:
        capabilities = " · ".join(CAPABILITY_LABELS[cap] for cap in sorted(model.capabilities))
        access = {
            "account": "Account / subscription",
            "api": "API key",
            "none": "No API key",
        }[model.backend.auth]
        value = f"{_inline_code(model.model)}\n{capabilities}\n{access}"
        if model.backend.kind in CLI_KINDS:
            value += "\nRequires isolated CLI runtime and authentication."
        name = (
            f"{'★ ' if model.name == selected else ''}{model.name} · "
            f"{BACKEND_LABELS[model.backend.kind]}"
        )
        if len(page.fields) >= 12 or len(page) + len(name) + len(value) > 5500:
            page = new_page()
        page.add_field(name=name, value=value, inline=True)
    if not models:
        page.add_field(name="No models available", value="Contact the bot administrator.")
    for index, page in enumerate(pages, 1):
        page.set_footer(
            text=f"Page {index}/{len(pages)} · Configured models; access may need setup"
        )
    return pages


class ModelPages(discord.ui.View):
    def __init__(self, pages: list[discord.Embed], owner_id: int):
        super().__init__(timeout=180)
        self.pages, self.owner_id, self.index = pages, owner_id, 0
        self.update_buttons()

    def update_buttons(self) -> None:
        self.previous.disabled = self.index == 0
        self.next.disabled = self.index == len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "This model menu belongs to another user. Open your own with /models.",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return False

    async def change_page(self, interaction: discord.Interaction, offset: int) -> None:
        self.index = min(max(self.index + offset, 0), len(self.pages) - 1)
        self.update_buttons()
        await interaction.response.edit_message(
            embed=self.pages[self.index],
            view=self,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.change_page(interaction, -1)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.change_page(interaction, 1)


def help_embed() -> discord.Embed:
    embed = discord.Embed(
        title="ChatGPT Discord Bot",
        description="Chat with your configured AI models and create media in Discord.",
        colour=COLOUR,
    )
    for title, text in (
        (
            "Chat & models",
            "**/chat** — Send a message\n**/models** — Browse models and capabilities\n"
            "**/provider** — Check your current model or choose another\n"
            "**/switchpersona** — Change the conversation's style",
        ),
        (
            "Conversation history",
            "**/private** · **/public** — Choose separate histories and reply visibility\n"
            "**/reset** — Clear the current history and restore defaults\n"
            "**/delete** — Clear both histories in this channel",
        ),
        (
            "Images & video",
            "**/image_search** — Find images on the web\n**/draw** — Generate or edit an image\n"
            "**/video** — Generate a video\n**/job** — Retrieve a submitted video\n"
            "Choose a model from each command's menu; capabilities vary by model.",
        ),
        (
            "Controls & CLI accounts",
            "**/cancel** — Stop waiting for outstanding requests\n"
            "**/cli_auth** — Owner-only CLI login, status and logout\n"
            "**/replyall** — Administrator control for configured automatic replies",
        ),
    ):
        embed.add_field(name=title, value=text, inline=False)
    embed.set_footer(
        text="History belongs to your account and this channel. API and CLI plan usage are separate."
    )
    return embed
