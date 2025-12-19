import logging
import math
import re
from html import unescape
import requests
import discord
from discord.ext import commands
from r2d7.XWing.cards import card_db
from r2d7.DiscordR3.discord_formatter import discord_formatter as fmt
from r2d7.XWing.list_formatter import ListFormatter
from typing import List, Union
logger = logging.getLogger(__name__)

class ListLookupCog(commands.Cog):
    # only one site does legacy squads, but allow for future options
    RE_LIST_URLS = [ re.compile(r'(https?://(xwing-legacy)\.com/(?:[^?/]*/)?\?(.*))') ]

    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.embeds = []
        self.db = card_db
        fmt.set_bot(self.bot)

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
        # Skip list lookups if 4-A7 is on the channel
        other_bot = discord.utils.get(message.channel.members, name='4-A7', discriminator='7543')
        if (other_bot is not None) and (other_bot.raw_status == 'online'):
            return
        # Card Lookup
        queries = []
        for list_re in self.RE_LIST_URLS:
            queries += list_re.findall(message.content)
        if len(queries) > 10:
            message.reply(content="Please use less than 10 search terms in your message")
        for q in queries:
            await self.do_list_lookup(q[0], message.reply, message)

    async def do_list_lookup_old(self, url, reply_callback, message=None):
        xws = self.get_xws(url)
        if xws:
            embeds: List[Union[discord.Embed, str]] = self.get_list_embeds(xws)  # First item returned is a string
            title = embeds[0]
            embeds = embeds[1:]
            if message:
                trailer =f"-# {message.author.display_name} requested this data.\n"
            else:
                trailer = ""

            if len(embeds) <= 4:
                await reply_callback(content=title, embeds=embeds, view=ConfirmDeleteView(message), footer=trailer)
            else:
                total = math.ceil(len(embeds)/4)
                count = 1
                while len(embeds) > 0:
                    if len(embeds) <= 4:
                        await reply_callback(content=f'{title} (part {count}/{total})', embeds=embeds[:4],
                                             view=ConfirmDeleteView(message), footer=trailer)
                    else:
                        await reply_callback(content=f'{title} (part {count}/{total})', embeds=embeds[:4],
                                             footer=trailer)
                    embeds = embeds[4:]
                    count += 1
        else:
            logger.error('Invalid URL - no XWS found')

    async def do_list_lookup(self, url, reply_callback, message=None):
        xws = self.get_xws(url)
        if xws:
            embeds: List[Union[discord.Embed, str]] = self.get_list_embeds(xws)  # First item returned is a string
            title = embeds[0]
            embeds = embeds[1:]
            if message:
                trailer =f"-# {message.author.display_name} requested this data.\n"
            else:
                trailer = ""

            char_count = 0
            embed_group = []
            embed_groups = []
            for embed in embeds:
                embed_chars = len(embed.description) + len(trailer)
                if (embed_chars + char_count) > 6000:
                    embed_groups.append(embed_group)
                    embed_group = [embed]
                    char_count = 0
                else:
                    embed_group.append(embed)
                    char_count += embed_chars
            embed_groups.append(embed_group)

            if len(embed_groups) == 1:
                await reply_callback(content=title, embeds=embeds, view=ConfirmDeleteView(message))
            else:
                for num, embed in enumerate(embed_groups):
                    if num < (len(embed_groups)-1):
                        await reply_callback(content=f'{trailer}\n{title}\n*(part {num + 1}/{len(embed_groups)})*',
                                             embeds=embed_groups[num])
                    else:
                        await reply_callback(content=f'*(part {num + 1}/{len(embed_groups)})*',
                                             embeds=embed_groups[num], view=ConfirmDeleteView(message))

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
            embeds.append(discord.Embed(description=line, color=fmt.get_faction_color(xws['faction'])))
        return embeds

class ConfirmDeleteView(discord.ui.View):
    def __init__(self, user_message):
        super().__init__()
        self.user_message = user_message

    @discord.ui.button(label='Delete URL', style=discord.ButtonStyle.green)
    async def confirm(self, button, interaction: discord.Interaction):
        await self.user_message.delete()
        await interaction.message.edit(view=None)

    @discord.ui.button(label='Do Nothing', style=discord.ButtonStyle.red)
    async def cancel(self, button, interaction: discord.Interaction):
        await interaction.message.edit(view=None)

def setup(bot): # this is called by Pycord to set up the cog
    bot.add_cog(ListLookupCog(bot)) # add the cog to the bot
