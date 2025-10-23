import logging

import discord
from ..discord_formatter import DiscordFormatter
from discord.ext import commands

logger = logging.getLogger(__name__)

class TestCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.formatter = DiscordFormatter()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info('Test cog ready')
        pass

    @discord.slash_command(description="Do not use!  Framework for random code testing.  Could crash the bot.")
    @discord.option("testme", type=discord.SlashCommandOptionType.string)
    async def testme(self, ctx, query: str):
        stuff = self.bot.app_emojis
        await ctx.respond(f'You said "{query}"')

def setup(bot): # this is called by Pycord to set up the cog
    bot.add_cog(TestCog(bot)) # add the cog to the bot

