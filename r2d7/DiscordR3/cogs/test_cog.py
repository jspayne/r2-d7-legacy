import logging

import discord
from r2d7.DiscordR3.discord_formatter import discord_formatter as fmt
from discord.ext import commands

logger = logging.getLogger(__name__)

class TestCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        fmt.set_bot(bot)

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info('Test cog ready')
        pass

    @discord.slash_command(description='Get user info from name')
    @discord.option("info", type=discord.SlashCommandOptionType.string)
    async def info(self, ctx, query: str):
        aname = query.split('#')[0]
        anum = query.split('#')[1]
        user = discord.utils.get(ctx.guild.members, name=aname, discriminator=anum)
        return await ctx.respond(user)

    @discord.slash_command(description="Do not use!  Framework for random code testing.  Could crash the bot.")
    @discord.option("testme", type=discord.SlashCommandOptionType.string)
    async def testme(self, ctx, query: str):
        await ctx.respond(f"Oh look, here's an emoji: {{crit}}".format_map(fmt.emoji_map))

def setup(bot): # this is called by Pycord to set up the cog
    bot.add_cog(TestCog(bot)) # add the cog to the bot

