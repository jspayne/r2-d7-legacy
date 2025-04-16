#!/usr/bin/env python
import logging
import os
import re
import asyncio
from dotenv import load_dotenv

import discord
from discord.ext import commands

from r2d7.listformatter import ListFormatter
from r2d7.cardlookup import CardLookup
from r2d7.factionlister import FactionLister
from r2d7.meta import Metawing
from r2d7.roller import Roller
from r2d7.talkback import Talkback
from r2d7.discorddroid import DiscordDroid

logger = logging.getLogger(__name__)
load_dotenv()

class Droid(
        DiscordDroid,
        ListFormatter,
        CardLookup,
        FactionLister,
        Metawing,
        Roller,
        Talkback):
    pass


intents = discord.Intents.default()
intents.message_content = True


class ConfirmDeleteView(discord.ui.View):
    def __init__(self, user_message, finalEmbed):
        super().__init__()
        self.user_message = user_message
        self.finalEmbed = finalEmbed

    @discord.ui.button(label='Delete URL', style=discord.ButtonStyle.green)
    async def confirm(self, button, interaction: discord.Interaction):
        if interaction.user == self.user_message.author:
            await self.user_message.delete()
            self.finalEmbed.set_footer(
                text=f"{self.user_message.author.display_name} requested this data.",
                icon_url=self.user_message.author.avatar.url
            )
            await interaction.message.edit(embed=self.finalEmbed, view=None)
        else:
            await interaction.response.send_message("That's not yours, you can't delete it!", ephemeral=True)

    @discord.ui.button(label='Do Nothing', style=discord.ButtonStyle.red)
    async def cancel(self, button, interaction: discord.Interaction):
        if interaction.user == self.user_message.author:
            await interaction.message.edit(embed=self.finalEmbed, view=None)
        else:
            await interaction.response.send_message("That's not yours!", ephemeral=True)


class DiscordClient(commands.Bot):
    def __init__(self, droid):
        super(DiscordClient, self).__init__(intents=intents)
        self.droid = droid
        self.emoji_map = {f":{emoji.name}:": str(emoji) for emoji in self.emojis}

        self._here = os.path.dirname(os.path.abspath(__file__))
        print(self._here)
        # load the cogsDirectory
        for filename in os.listdir(os.path.join(self._here, "cogs")):
            if filename.endswith("py"):
                self.load_extension(f"r2d7.discordR2.cogs.{filename[:-3]}")
                logger.info(f"{filename} loaded.")

    async def on_ready(self):
        logger.info(f"Bot online as {self.user}")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        logger.debug(f"Message: {message}\nContent: {message.clean_content}")

        bot_has_message_permissions = message.guild and message.channel.permissions_for(message.guild.me).manage_messages

        # Check for new data
        if self.droid.needs_update():
            self.droid.load_data()

        if self.droid.needs_update(points_database="XWA"):
            self.droid.load_data("XWA")

        responses = None

        if not message.guild:
            for regex, handle_method in self.droid._dm_handlers.items():
                match = regex.search(message.clean_content)
                if match:
                    responses = handle_method(match[1])
                    if responses:
                        break

        if not responses:
            for regex, handle_method in self.droid._handlers.items():
                logger.debug(f"Checking {regex}")
                match = regex.search(message.clean_content)
                if match:
                    responses = handle_method(match[1])
                    if responses:
                        break

        if responses:
            # If there are multiple matches, allow the user to select one, up to 9 matches.
            if len(responses) > 1:
                choices = [
                    f"**{i+1})** {response[0]}"
                    for i, response in enumerate(responses)
                ]
                multipleChoiceEmbed = discord.Embed(title="Multiple Cards found.")
                multipleChoiceEmbed.set_footer(
                    text="Type your selection below, or 'x' to cancel."
                ).add_field(
                    name="Cards matching query:",
                    value='\n'.join(choices)
                )
                multipleChoiceEmbedMessage = await message.channel.send(embed=multipleChoiceEmbed)
                try:
                    def check(m):
                        lowercaseMessage = m.content.lower()
                        isValid = lowercaseMessage in ['x'] + [str(n) for n in range(1, 16)]
                        if lowercaseMessage.isnumeric():
                            isValid = 1 <= int(lowercaseMessage) <= len(responses)

                        return m.author.id == message.author.id and isValid

                    choiceSelectionMessage = await self.wait_for(
                        event='message',
                        check=check,
                        timeout=20
                    )
                    userCanceled = choiceSelectionMessage.content.lower() == 'x'
                    if not userCanceled:
                        choiceSelectionNumber = int(choiceSelectionMessage.content)
                        responses = [responses[choiceSelectionNumber - 1]]

                    if bot_has_message_permissions:
                        await choiceSelectionMessage.delete()
                        await multipleChoiceEmbedMessage.delete()

                    # if user typed 'x', cancel the operation.
                    if userCanceled:
                        await message.delete()
                        return

                except asyncio.TimeoutError:
                    if bot_has_message_permissions:
                        await multipleChoiceEmbedMessage.delete()
                    return

            # Show embeds for all data pulled.
            for response in responses:
                emoji_map = {f":{emoji.name}:": str(emoji) for emoji in self.emojis}

                current_message = ''
                for line in response:
                    fixed_line = line
                    print(line)
                    for slack_style, discord_style in emoji_map.items():
                        if isinstance(fixed_line, str):
                            fixed_line = fixed_line.replace(
                                slack_style, discord_style)
                        else:
                            fixed_line = ' '.join(fixed_line).replace(slack_style, discord_style)
                    # Set maximum size for embed to maximum content size of embed minus the maximum for footer
                    if len(current_message) + 2 + len(fixed_line) < 3952:
                        current_message += f"\n{fixed_line}"
                    else:
                        embed = discord.Embed(description=current_message)
                        await message.channel.send(embed=embed)
                        current_message = fixed_line

                finalEmbed = discord.Embed(description=current_message)
                finalMessage = await message.channel.send(
                    embed=finalEmbed,
                    view=ConfirmDeleteView(message, finalEmbed) if bot_has_message_permissions else None
                )
            #
            # # allow the user to delete their query message
            # if bot_has_message_permissions:
            #     view = ConfirmDeleteView(message)
            #     await message.channel.send("Delete your message?", view=view)



def main():
    debug = os.getenv('DEBUG', False)
    log_level = 'DEBUG' if debug else 'INFO'
    logging.basicConfig(
        format='%(asctime)s [%(process)d] Discord - %(levelname)s: %(message)s',
        level=log_level
    )

    # discord_token = os.getenv("DISCORD_TOKEN", None)
    discord_token = os.getenv("DEV_TOKEN", None)
    logging.info(f"discord token: {discord_token}")

    droid = Droid()
    if discord_token:
        logging.info("DISCORD_TOKEN env var set")
        bot = DiscordClient(droid)
        bot.run(discord_token)
    else:
        logging.error("No discord token found, exiting.")
        return


if __name__ == "__main__":
    main()
