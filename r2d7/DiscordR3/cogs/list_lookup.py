import logging
import re
from enum import Enum
from html import unescape
import requests
import discord
from discord.ext import commands
from r2d7.DiscordR3.cogs import card_db
from r2d7.XWing.list_formatter import ListFormatter

logger = logging.getLogger(__name__)

class ListLookupCog(commands.Cog):
    # only one site does legacy squads, but allow for future options
    RE_LIST_URLS = [ re.compile(r'(https?://(xwing-legacy)\.com/(?:[^?/]*/)?\?(.*))') ]

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.embeds = []
        self.db = card_db

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info('List lookup cog ready')

    @commands.slash_command(description="Look up X-Wing list from URL")
    @discord.option("URL", type=discord.SlashCommandOptionType.string)
    async def list(self, ctx: discord.ApplicationContext, url):
        await self.do_list_lookup(url, ctx.respond)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:  # Don't respond to myself or other bots.
            return
        await self.do_list_lookup(message, message.reply)

    async def do_list_lookup(self, url, reply_callback):
        xws = self.get_xws(url)
        if xws:
            embeds = self.get_list_embeds(xws)
            await reply_callback(content=embeds[0], embeds=embeds[1:])
        else:
            logger.error('Invalid URL - no XWS found')

    def get_xws(self, message):
        match = None
        for regex in self.RE_LIST_URLS:
            match = regex.match(message)
            if match:
                break
        else:
            logger.debug(f"Unrecognised URL: {message}")
            return None

        xws_url = None
        if match[2] == 'xwing-legacy':
            xws_url = f'https://rollbetter-linux.azurewebsites.net/lists/xwing-legacy?{match[0]}'
        if xws_url:
            xws_url = unescape(xws_url)
            logging.info(f"Requesting {xws_url}")
            response = requests.get(xws_url)
            if response.status_code != 200:
                logger.error(f"GET {xws_url} request failed with status code {response.status_code}")
                return None
            data = response.json()
            if 'message' in data:
                logger.error(f"YASB error: ({data['message']}")
                return None
            return data

    def get_list_embeds(self, xws):
        formatter = ListFormatter(self.db, xws)
        output = formatter.print_list()
        embeds = [output[0]]
        for line in output[1:]:
            embeds.append(discord.Embed(description=line))
        return embeds

def setup(bot): # this is called by Pycord to set up the cog
    bot.add_cog(ListLookupCog(bot)) # add the cog to the bot
