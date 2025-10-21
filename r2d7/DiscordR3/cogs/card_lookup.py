import logging
import re
import random

import discord
from discord.ext import commands
from . import card_db
from ...XWing.cards import Ship

logger = logging.getLogger(__name__)

class CardLookupCog(commands.Cog):
    RE_IMAGE = re.compile(r'\{\{(.*?)}}')
    RE_CARD = re.compile(r'\[\[(.*?)]]')
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.embeds = []
        self.db = card_db

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info('Card lookup cog ready')

    @commands.slash_command(description="Look up any X-Wing card")
    @discord.option("query", type=discord.SlashCommandOptionType.string)
    async def card(self, ctx: discord.ApplicationContext, query):
        await self.do_card_lookup(query, ctx.respond)

    @commands.slash_command(description="Draw a random Critical Hit")
    async def crit(self, ctx):
        logger.debug(f'Drawing a random Critical Hit')
        card = random.choice(list(self.db.damage_deck.values()))
        await ctx.respond(embeds=get_card_embeds(card))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:  # Don't respond to myself or other bots.
            return
        # Card Lookup
        queries = self.RE_CARD.findall(message.content)
        if len(queries) > 10:
            message.reply(content="Please use less than 10 search terms in your message")
        for q in queries:
            await self.do_card_lookup(q, message.reply)

    async def do_card_lookup(self, query, reply_callback):
        self.db.update_data()  # this is rate limited by the db
        logger.debug(f'Card query: {query}')
        results = self.db.search_cards(query)
        if len(results) == 1:
            if isinstance(results[0], Ship):
                ship_embed = discord.Embed(description=str(results[0]))
                await reply_callback(embed=ship_embed, view=PilotSelect(results[0]))
            else:
                await reply_callback(embeds=get_card_embeds(results[0]))
        elif len(results) > 1:
            await reply_callback(view=SelectCard(results))
        else:
            await reply_callback(content=f'No results found for query: {query}')

def setup(bot: commands.Bot):
    bot.add_cog(CardLookupCog(bot))

class SelectCard(discord.ui.View):
    def __init__(self, results_from_lookup):
        self.embeds = []
        self.timeout = 30
        self.all_results = {card.unique_name: card for card in results_from_lookup}
        options = []
        for name, card in self.all_results.items():
            select = card.select_line()
            select['value'] = name
            options.append(discord.SelectOption(**select))
        super().__init__()
        # Not using the select decorator because the choice list is dynamic
        dropdown = discord.ui.Select(
            placeholder=f"Select up to {min(5, len(self.all_results))}",
            min_values=1, max_values=min(5, len(self.all_results)),
            options=options,
            row=0
        )
        dropdown.callback = self.card_select_callback
        self.add_item(dropdown)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel_callback(self, button, interaction: discord.Interaction): # noqa: button is part of the API
        await interaction.response.edit_message(content="Cancelling...", view=None, delete_after=1)

    async def card_select_callback(self, interaction: discord.Interaction):
        card_embeds = []
        for name in interaction.data['values']:
            card = self.all_results[name]
            if isinstance(card, Ship):
                await interaction.response.send_message(embed=discord.Embed(description=str(card)), view=PilotSelect(card))
            else:
                card_embeds.extend(get_card_embeds(card))
                await interaction.response.edit_message(embeds=card_embeds, view=None)

class PilotSelect(discord.ui.View):
    def __init__(self, ship):
        self.all_pilots = {pilot.unique_name: pilot for pilot in ship.pilots.values()}
        self.embeds = []
        self.timeout = 30
        super().__init__()

        for group, pilots in ship.get_grouped_pilots().items():
            options = []
            for pilot in pilots:
                select = pilot.pilot_select_line()
                select['value'] = pilot.unique_name
                options.append(select)
            # options = [discord.SelectOption(**select) for select in sorted(options, key=lambda item: item['emoji'], reverse=True)]
            options = [discord.SelectOption(**select) for select in options]
            dropdown = discord.ui.Select(
                placeholder=f"{group}",
                min_values=1, max_values=min(5, len(options)),
                options=options
            )
            dropdown.callback = self.pilot_select_callback
            self.add_item(dropdown)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=4)
    async def cancel_callback(self, button, interaction: discord.Interaction): # noqa: button is part of the API
        await interaction.response.edit_message(content="Cancelling...", view=None, delete_after=1)

    async def pilot_select_callback(self, interaction: discord.Interaction):
        card_embeds = []
        for name in interaction.data['values']:
            card = self.all_pilots[name]
            card_embeds.extend(get_card_embeds(card))
        await interaction.response.send_message(embeds=card_embeds)



def get_card_embeds(card):
    embeds = []
    if card.sides and len(card.sides) > 1:
        embed = discord.Embed(description=card.print_header(), thumbnail=card.sides[0].image)
        for side in card.sides:
            embed.add_field(name=side.bold(side.title), value=card.print_side(side), inline=False)
        embeds.append(embed)
    else:
        image = card.get_image()
        if image:
            embeds.append(discord.Embed(description=str(card), thumbnail=(card.image or card.sides[0].image)))
        else:
            embeds.append(discord.Embed(description=str(card)))
    return embeds

