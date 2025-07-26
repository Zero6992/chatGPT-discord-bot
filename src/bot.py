import os
import asyncio
import discord
from discord import app_commands
from typing import Optional

from src.aclient import discordClient
from src.providers import ProviderType
from src import log, personas
from src.log import logger


def run_discord_bot():
    @discordClient.event
    async def on_ready():
        await discordClient.send_start_prompt()
        await discordClient.tree.sync()
        loop = asyncio.get_event_loop()
        loop.create_task(discordClient.process_messages())
        logger.info(f'{discordClient.user} is now running!')

    @discordClient.tree.command(name="chat", description="Have a chat with AI")
    async def chat(interaction: discord.Interaction, *, message: str):
        # Input validation
        if len(message) > 2000:
            await interaction.response.send_message(
                "❌ Message too long (max 2000 characters)", 
                ephemeral=True
            )
            return
        
        # Sanitize input
        message = message.replace('\x00', '')  # Remove null bytes
        message = message.strip()
        
        if not message:
            await interaction.response.send_message(
                "❌ Please provide a message", 
                ephemeral=True
            )
            return
        
        if discordClient.is_replying_all:
            await interaction.response.defer(ephemeral=False)
            await interaction.followup.send(
                "> **WARN: You already on replyAll mode. If you want to use the Slash Command, switch to normal mode by using `/replyall` again**")
            logger.warning("\x1b[31mYou already on replyAll mode, can't use slash command!\x1b[0m")
            return
        if interaction.user == discordClient.user:
            return
        username = str(interaction.user)
        discordClient.current_channel = interaction.channel
        logger.info(
            f"\x1b[31m{username}\x1b[0m : /chat [{message}] in ({discordClient.current_channel})")

        await discordClient.enqueue_message(interaction, message)

    @discordClient.tree.command(name="provider", description="Switch AI provider and model")
    async def provider(interaction: discord.Interaction):
        """Interactive provider and model selection"""
        
        # Create provider selection dropdown
        class ProviderSelect(discord.ui.Select):
            def __init__(self):
                options = []
                available_providers = discordClient.provider_manager.get_available_providers()
                
                for provider_type in available_providers:
                    emoji_map = {
                        ProviderType.FREE: "🆓",
                        ProviderType.OPENAI: "🟢",
                        ProviderType.CLAUDE: "🟣",
                        ProviderType.GEMINI: "🔵",
                        ProviderType.GROK: "⚫"
                    }
                    
                    options.append(discord.SelectOption(
                        label=provider_type.value.capitalize(),
                        value=provider_type.value,
                        emoji=emoji_map.get(provider_type, "🤖"),
                        default=(provider_type == discordClient.provider_manager.current_provider)
                    ))
                
                super().__init__(
                    placeholder="Select a provider...",
                    options=options,
                    min_values=1,
                    max_values=1
                )
            
            async def callback(self, interaction: discord.Interaction):
                selected_provider = ProviderType(self.values[0])
                
                # Get models for selected provider
                provider = discordClient.provider_manager.get_provider(selected_provider)
                models = provider.get_available_models()
                
                if not models:
                    discordClient.switch_provider(selected_provider)
                    await interaction.response.send_message(
                        f"✅ Switched to **{selected_provider.value}** provider",
                        ephemeral=True
                    )
                    return
                
                # Create model selection dropdown
                class ModelSelect(discord.ui.Select):
                    def __init__(self):
                        options = [
                            discord.SelectOption(
                                label="Auto (Best Available)",
                                value="auto",
                                description="Let the provider choose the best model",
                                emoji="🎯"
                            )
                        ]
                        
                        for model in models[:24]:  # Discord limit is 25 options
                            desc = model.description[:100] if model.description else ""
                            emoji = "🖼️" if model.supports_image_generation else "💬"
                            
                            options.append(discord.SelectOption(
                                label=model.name,
                                value=model.name,
                                description=desc,
                                emoji=emoji
                            ))
                        
                        super().__init__(
                            placeholder="Select a model...",
                            options=options,
                            min_values=1,
                            max_values=1
                        )
                    
                    async def callback(self, interaction: discord.Interaction):
                        selected_model = self.values[0]
                        discordClient.switch_provider(selected_provider, selected_model)
                        
                        await interaction.response.send_message(
                            f"✅ Switched to **{selected_provider.value}** provider with **{selected_model}** model",
                            ephemeral=True
                        )
                
                model_view = discord.ui.View()
                model_view.add_item(ModelSelect())
                
                await interaction.response.send_message(
                    f"Select a model for **{selected_provider.value}** provider:",
                    view=model_view,
                    ephemeral=True
                )
        
        # Create and send the provider selection view
        provider_view = discord.ui.View()
        provider_view.add_item(ProviderSelect())
        
        # Get current info
        info = discordClient.get_current_provider_info()
        
        embed = discord.Embed(
            title="🤖 AI Provider Settings",
            description=f"**Current Provider:** {info['provider']}\n**Current Model:** {info['current_model']}",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(
            embed=embed,
            view=provider_view,
            ephemeral=True
        )

    @discordClient.tree.command(name="draw", description="Generate an image")
    async def draw(interaction: discord.Interaction, *, prompt: str):
        # Input validation
        if len(prompt) > 500:
            await interaction.response.send_message(
                "❌ Prompt too long (max 500 characters)", 
                ephemeral=True
            )
            return
        
        prompt = prompt.strip()
        if not prompt:
            await interaction.response.send_message(
                "❌ Please provide a prompt", 
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Generate image using current provider
            image_url = await discordClient.generate_image(prompt)
            
            embed = discord.Embed(
                title="🎨 Generated Image",
                description=f"**Prompt:** {prompt}",
                color=discord.Color.green()
            )
            embed.set_image(url=image_url)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            await interaction.followup.send(
                f"❌ Failed to generate image: {str(e)}"
            )

    @discordClient.tree.command(name="switchpersona", description="Switch AI personality")
    async def switchpersona(interaction: discord.Interaction, persona: str):
        user_id = str(interaction.user.id)
        
        try:
            available_personas = personas.get_available_personas(user_id)
            
            if persona not in available_personas:
                await interaction.response.send_message(
                    f"❌ Invalid persona. Available personas: {', '.join(available_personas)}",
                    ephemeral=True
                )
                return
            
            # Check permissions for jailbreak personas
            if personas.is_jailbreak_persona(persona):
                try:
                    personas.get_persona_prompt(persona, user_id)
                except PermissionError:
                    await interaction.response.send_message(
                        f"❌ You don't have permission to use the '{persona}' persona. "
                        f"This persona is restricted to administrators only.",
                        ephemeral=True
                    )
                    return
                
                # Warn about jailbreak usage
                await interaction.response.send_message(
                    f"⚠️ **WARNING**: The '{persona}' persona is designed to bypass safety measures. "
                    f"Use at your own risk and responsibility. This action has been logged.",
                    ephemeral=False
                )
                logger.warning(f"User {user_id} activated jailbreak persona: {persona}")
            else:
                await interaction.response.defer(ephemeral=False)
            
            await discordClient.switch_persona(persona, user_id)
            
            message = f"🎭 Switched to **{persona}** persona"
            if personas.is_jailbreak_persona(persona):
                message += " (Jailbreak Mode Active - Admin Only)"
            
            if hasattr(interaction, 'followup'):
                await interaction.followup.send(message)
            else:
                await interaction.channel.send(message)
                
        except Exception as e:
            logger.error(f"Error switching persona: {e}")
            await interaction.response.send_message(
                f"❌ Failed to switch persona: {str(e)}",
                ephemeral=True
            )

    @discordClient.tree.command(name="private", description="Toggle private access")
    async def private(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        if not discordClient.isPrivate:
            discordClient.isPrivate = not discordClient.isPrivate
            logger.warning("\x1b[31mSwitch to private mode\x1b[0m")
            await interaction.followup.send(
                "> **INFO: Next, the response will be sent as ephemeral message and only visible to you.**")
        else:
            discordClient.isPrivate = not discordClient.isPrivate
            logger.info("Switch to public mode")
            await interaction.followup.send(
                "> **INFO: Next, the response will be sent as normal message and visible to everyone.**")

    @discordClient.tree.command(name="replyall", description="Toggle replyAll access")
    async def replyall(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        if discordClient.is_replying_all:
            discordClient.is_replying_all = False
            await interaction.followup.send("> **INFO: The bot will only respond to /chat commands.**")
            logger.warning("\x1b[31mSwitch to normal mode\x1b[0m")
        else:
            discordClient.is_replying_all = True
            await interaction.followup.send("> **INFO: The bot will respond to all messages in this channel.**")
            logger.info("Switch to replyAll mode")

    @discordClient.tree.command(name="reset", description="Clear conversation history")
    async def reset(interaction: discord.Interaction):
        discordClient.reset_conversation_history()
        await interaction.response.send_message(
            "🔄 Conversation history has been cleared. Starting fresh!",
            ephemeral=False
        )

    @discordClient.tree.command(name="help", description="Show all available commands")
    async def help(interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 AI Discord Bot - Help",
            description="Here are all available commands:",
            color=discord.Color.blue()
        )
        
        commands = [
            ("💬 **Chat Commands**", [
                ("/chat [message]", "Chat with the AI"),
                ("/reset", "Clear conversation history"),
                ("/replyall", "Toggle bot responding to all messages")
            ]),
            ("🤖 **Provider & Model**", [
                ("/provider", "Switch AI provider and model interactively")
            ]),
            ("🎨 **Image Generation**", [
                ("/draw [prompt]", "Generate an image from text")
            ]),
            ("🎭 **Personas**", [
                ("/switchpersona [name]", "Change AI personality"),
                ("Available", "standard, creative, technical, casual"),
                ("Admin Only", "jailbreak-v1, jailbreak-v2, jailbreak-v3 (restricted)")
            ]),
            ("⚙️ **Settings**", [
                ("/private", "Toggle private/public responses"),
                ("/help", "Show this help message")
            ])
        ]
        
        for category, cmds in commands:
            value = "\n".join([f"`{cmd}` - {desc}" for cmd, desc in cmds])
            embed.add_field(name=category, value=value, inline=False)
        
        # Add provider info
        info = discordClient.get_current_provider_info()
        embed.add_field(
            name="📊 Current Settings",
            value=f"**Provider:** {info['provider']}\n**Model:** {info['current_model']}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # Handle regular messages when replyall is on
    @discordClient.event
    async def on_message(message):
        if discordClient.is_replying_all:
            if message.author == discordClient.user:
                return
            
            if discordClient.replying_all_discord_channel_id:
                if message.channel.id != int(discordClient.replying_all_discord_channel_id):
                    return
            
            username = str(message.author)
            user_message = message.content
            discordClient.current_channel = message.channel
            
            logger.info(f"\x1b[31m{username}\x1b[0m : {user_message} in ({message.channel})")
            await discordClient.enqueue_message(message, user_message)

    # Run the bot
    discordClient.run(os.getenv("DISCORD_BOT_TOKEN"))