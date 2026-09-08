"""Discord delivery always uses the request's original transport and visibility."""

import io
from typing import Any

import discord

from src.art import Artifact
from src.domain import BotError
from src.search import SearchImage


async def send_text(target: Any, content: str, *, private: bool) -> None:
    mentions = discord.AllowedMentions.none()
    if hasattr(target, "followup"):

        async def send(**kwargs: Any) -> None:
            await target.followup.send(ephemeral=private, allowed_mentions=mentions, **kwargs)
    else:
        if private:
            raise BotError("Private replies require a slash command.")

        async def send(**kwargs: Any) -> None:
            await target.channel.send(allowed_mentions=mentions, **kwargs)

    # Preserve code fences and avoid an unbounded series of Discord sends.
    if len(content) > 1900:
        buffer = io.BytesIO(content.encode())
        file = discord.File(buffer, filename="response.txt")
        try:
            await send(content="The full response is attached.", file=file)
        finally:
            file.close()
            buffer.close()
    else:
        await send(content=content)


async def send_artifact(target: Any, artifact: Artifact, *, private: bool, maximum: int) -> None:
    guild = getattr(target, "guild", None)
    limit = min(maximum, getattr(guild, "filesize_limit", 10 * 1024 * 1024))
    if len(artifact.data) > limit:
        raise BotError("Generated media exceeds this Discord server's attachment limit.")
    buffer = io.BytesIO(artifact.data)
    file = discord.File(buffer, filename=artifact.filename)
    try:
        await target.followup.send(
            file=file, ephemeral=private, allowed_mentions=discord.AllowedMentions.none()
        )
    finally:
        file.close()
        buffer.close()


async def send_search_images(target: Any, images: list[SearchImage], *, private: bool) -> None:
    embeds = []
    for result in images[:3]:
        embed = discord.Embed(
            title=discord.utils.escape_markdown(result.title)[:256], url=result.url
        )
        embed.set_image(url=result.url)
        embed.set_footer(text="Search result · linked from the original image host")
        embeds.append(embed)
    await target.followup.send(
        content="Images found on the web. Preview availability depends on the source website.",
        embeds=embeds,
        ephemeral=private,
        allowed_mentions=discord.AllowedMentions.none(),
    )
