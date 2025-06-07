import contextlib
import discord
from discord.ext import commands
from ...XWing.cards import XwingDB

class CardLookupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embeds = []
        self.db = XwingDB()

    @commands.slash_command(description="Look up a card")
    @discord.option("query", type=discord.SlashCommandOptionType.string)
    async def card(self, ctx, query):
        results = self.db.search_cards(query)
        if len(results) > 1:
            await ctx.respond(view=SelectCard(results), ephemeral=True)
        else:
            await ctx.respond(content=f'No cards found for "{query}"', ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(CardLookupCog(bot))

class SelectCard(discord.ui.View):
    def __init__(self, results_from_lookup):
        self.embeds = []
        self.timeout = 30
        self.all_results = {card.unique_name: card for card in results_from_lookup}
        options = []
        for name, card in self.all_results.items():
            emoji = None
            label = card.print_header(no_links=True).strip()
            if label[0] == '{':  # starts with an emoji
                emoji = label.split('}')[0] + '}'
                emoji = emoji.format_map(card.emoji_map)
                label = label.split('} ')[1]
            options.append(discord.SelectOption(label=label, value=name, emoji=emoji))
        super().__init__()
        dropdown = discord.ui.Select(
            placeholder=f"Select up to {min(5, len(self.all_results))}",
            min_values=1, max_values=min(5, len(self.all_results)),
            options=options
        )
        dropdown.callback = self.card_select_callback
        self.add_item(dropdown)

    async def card_select_callback(self, interaction: discord.Interaction):
        card_embeds = []
        for name in interaction.data['values']:
            card_embeds.append(discord.Embed(description=str(self.all_results[name])))
        await interaction.response.edit_message(embeds=card_embeds, view=None)
