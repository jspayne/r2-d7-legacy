import json
import re

import discord
import os
from discord.ext import commands


class SelectCard(discord.ui.View):
    def __init__(self, results_from_lookup, bot):
        self.bot = bot
        self.embeds = []
        super().__init__()

        self.allResults = results_from_lookup
        self.label_to_fullResult_dict = {}

        for result in self.allResults:
            firstLine = result[0]
            cardType = firstLine.split()[0].replace(':', '')
            cardTrueName = firstLine.split('**[')[1].split('](')[0]
            label = f"{cardTrueName} ({cardType})"
            self.label_to_fullResult_dict[label] = result

        dropdown = discord.ui.Select(
            placeholder=f"Select up to {min(5, len(self.allResults))}",
            min_values=1, max_values=min(5, len(self.allResults)),
            options=[
                discord.SelectOption(label=cardLabel)  # emoji = pattern.match(cardName)[0] would go here
                for cardLabel in self.label_to_fullResult_dict
            ]
        )
        dropdown.callback = self.cardSelectCallback
        self.add_item(dropdown)

    async def cardSelectCallback(self, interaction: discord.Interaction):
        selected_card_labels = interaction.data['values']
        fullCards = [self.label_to_fullResult_dict[label] for label in selected_card_labels]

        emoji_map = {f":{emoji.name}:": str(emoji) for emoji in self.bot.emojis}

        for fullCard in fullCards:
            current_message = ''
            for line in fullCard:
                fixed_line = line
                for slack_style, discord_style in emoji_map.items():
                    fixed_line = fixed_line.replace(
                        slack_style, discord_style)
                # Set maximum size for embed to maximum content size of embed minus the maximum for footer
                if len(current_message) + 2 + len(fixed_line) < 3952:
                    current_message += f"\n{fixed_line}"
                else:
                    embed = discord.Embed(description=current_message)
                    self.embeds.append(embed)
                    current_message = fixed_line

            self.embeds.append(discord.Embed(description=current_message))
        await interaction.response.edit_message(embeds=self.embeds, view=None)


class LookupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embeds = []

    @commands.slash_command(
        description="Look up a card"
    )
    async def card(self, ctx: discord.ApplicationContext, keyword):
        responses = None
        if self.bot.droid.needs_update():
            self.bot.droid.load_data()

        if not ctx.guild:
            for regex, handle_method in self.bot.droid._dm_handlers.items():
                if match := regex.search(f"[[{keyword}]]"):
                    responses = handle_method(match[1])
                    if responses:
                        break

        if not responses:
            for regex, handle_method in self.bot.droid._handlers.items():
                if match := regex.search(f"[[{keyword}]]"):
                    responses = handle_method(match[1])
                    if responses:
                        break

        if responses:
            if len(responses) > 1:
                await ctx.respond(view=SelectCard(responses, self.bot), ephemeral=True)

            else:
                emoji_map = {f":{emoji.name}:": str(emoji) for emoji in self.bot.emojis}

                current_message = ''
                for line in responses[0]:
                    fixed_line = line
                    for slack_style, discord_style in emoji_map.items():
                        fixed_line = fixed_line.replace(
                            slack_style, discord_style)
                    # Set maximum size for embed to maximum content size of embed minus the maximum for footer
                    if len(current_message) + 2 + len(fixed_line) < 5500:
                        current_message += f"\n{fixed_line}"
                    else:
                        embed = discord.Embed(description=current_message)
                        self.embeds.append(embed)
                        current_message = fixed_line

                self.embeds.append(discord.Embed(description=current_message))
                await ctx.respond(embeds=self.embeds, view=None, ephemeral=True)



def setup(bot: commands.Bot):
    bot.add_cog(LookupCog(bot))
