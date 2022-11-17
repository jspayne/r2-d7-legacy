import contextlib
import json
import re

import discord
import os
from discord.ext import commands


class SelectCard(discord.ui.View):
    def __init__(self, results_from_lookup, bot):
        self.bot = bot
        self.embeds = []
        self.timeout = 30
        super().__init__()
        self.allResults = results_from_lookup
        self.label_to_fullResult_dict = {}
        self.label_to_emoji_dict = {}

        legal_game_mode_emoji = {
            "Standard": "✅ ",
            "Extended": "⚠ ",
            "Epic": "🪐 "
        }
        restriction_to_emoji = {
            "Rebel": "rebel",
            "Empire": "imperial",
            "First Order": "first_order",
            "Republic": "galacticrepublic",
            "Resistance": "resistance",
            "Separatist": "separatistalliance",
            "Scum": "scum"
        }
        faction_emoji = {
            "rebel": "<:0factionRebel:627670387051986966>",
            "imperial": "<:0factionEmpire:627670390071623681>",
            "first_order": "<:0factionFirstOrder:627670812626911244>",
            "scum": "<:0factionScum:627685784907939841>",
            "galacticrepublic": "<:0factionRepublic:627670389333426206>",
            "resistance": "<:0factionResistance:627670388993949699>",
            "separatistalliance": "<:0factionSeparatist:627685785440747520>"
        }

        for result in self.allResults:
            # print(result)
            firstLine, secondLine = result[:2]
            # accounts for double-slot cards, and strips colons
            cardType = firstLine.split()[0].replace("::", "+")[1:-1]
            unique_pips = None
            if "•" in firstLine:
                unique_pips = f"{firstLine.split()[1]} "

            try:
                cardTrueName = firstLine.split(' **[')[1].split('](')[0]
            except IndexError:
                cardTrueName = firstLine.replace("**", "").split(": ")[1]

            # Grabs the card identifier i.e. "Red Five" for Luke
            with contextlib.suppress(IndexError):
                identifier = firstLine.split('**: *')[1].split('*')[0]
                cardTrueName += f" – {identifier}"

            restrictions = " ".join(secondLine.split()[1:]).replace(',', '').replace('*', '') if "Restrictions" in secondLine else None

            faction = None
            legality_emoji = None
            emoji = None
            if not restrictions:
                faction = secondLine.split(": ")[0][1:]
            if "[Standard]" in firstLine:
                legality_emoji = legal_game_mode_emoji['Standard']
            elif "[Extended]" in firstLine:
                legality_emoji = legal_game_mode_emoji['Extended']
            elif "[Epic]" in firstLine:
                legality_emoji = legal_game_mode_emoji['Epic']

            if restrictions in restriction_to_emoji:
                emoji = faction_emoji[restriction_to_emoji[restrictions]]
            elif faction in faction_emoji:
                emoji = faction_emoji[faction]

            label = f"{legality_emoji or ''}{unique_pips or ''}{cardTrueName} ({cardType})"
            if restrictions:
                label += f", {restrictions}"
            self.label_to_fullResult_dict[label] = result
            self.label_to_emoji_dict[label] = emoji

        dropdown = discord.ui.Select(
            placeholder=f"Select up to {min(5, len(self.allResults))}",
            min_values=1, max_values=min(5, len(self.allResults)),
            options=[
                discord.SelectOption(label=cardLabel, emoji=self.label_to_emoji_dict[cardLabel])  # emoji = pattern.match(cardName)[0] would go here
                for cardLabel in self.label_to_fullResult_dict
            ]
        )
        dropdown.callback = self.cardSelectCallback
        self.add_item(dropdown)

    def create_card_embeds(self, card_data):
        emoji_map = {f":{emoji.name}:": str(emoji) for emoji in self.bot.emojis}
        current_message = ''
        for line in card_data:
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

    async def cardSelectCallback(self, interaction: discord.Interaction):
        selected_card_labels = interaction.data['values']
        fullCards = [
            self.label_to_fullResult_dict[label]
            for label in selected_card_labels
        ]
        self.embeds = []
        for fullCard in fullCards:
            self.create_card_embeds(fullCard)

        await interaction.response.edit_message(embeds=self.embeds, view=None)


class LookupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embeds = []

    @commands.slash_command(
        description="Look up a card"
    )
    async def card(self, ctx: discord.ApplicationContext, query):
        results = None
        if self.bot.droid.needs_update():
            self.bot.droid.load_data()

        if not ctx.guild:
            for regex, handle_method in self.bot.droid._dm_handlers.items():
                if match := regex.search(f"[[{query}]]"):
                    results = handle_method(match[1])
                    if results:
                        break

        if not results:
            for regex, handle_method in self.bot.droid._handlers.items():
                if match := regex.search(f"[[{query}]]"):
                    results = handle_method(match[1])
                    if results:
                        break
        if not results:
            await ctx.respond("No cards found matching your query.", ephemeral=True)
            return

        self.embeds = []
        if len(results) > 1:
            await ctx.respond(view=SelectCard(results, self.bot), ephemeral=True)

        else:
            emoji_map = {f":{emoji.name}:": str(emoji) for emoji in self.bot.emojis}

            current_message = ''
            for line in results[0]:
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
            await ctx.respond(embeds=self.embeds, view=None, ephemeral=True)


def setup(bot: commands.Bot):
    bot.add_cog(LookupCog(bot))
