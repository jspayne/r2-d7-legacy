import logging

import discord
from ..discord_formatter import DiscordFormatter
from discord.ext import commands
from ...XWing.roller import ModdedRoll, VsRoll
from ...XWing.dice import DieType
import random
import re

logger = logging.getLogger(__name__)

class DiceRollerCog(commands.Cog):
    re_vs = re.compile('\\b(?P<vs>(vs)|(versus)|(v))\\b', re.I)
    re_syntax = re.compile('\\b((syntax)|(help))\\b', re.I)
    re_numeric = re.compile('\\bd(?P<num>[0-9]+)\\b', re.I)
    re_scenario = re.compile('\\b((scenario)|(mission))\\b', re.I)

    def __init__(self, bot):
        self.bot = bot
        self.formatter = DiscordFormatter()

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info('Dice roller cog ready')

    @discord.slash_command(description="Roll dice")
    @discord.option("query", type=discord.SlashCommandOptionType.string)
    async def roll(self, ctx, query: str):
        resp = self.roll_dice(query)
        if isinstance(resp, list):
            resp = '\n'.join(resp)
        await ctx.respond(resp.format_map(self.formatter.emoji_map))

    def roll_dice(self, query):
        if self.re_syntax.search(query):
            return self.roll_syntax()
        elif match_numeric := self.re_numeric.search(query):
            return self.roll_numeric(match_numeric)
        elif self.re_scenario.search(query):
            return self.roll_scenario()
        else:
            try:
                if match_vs := self.re_vs.search(query):
                    roll_strings = query.split(match_vs.group('vs'))
                    modded_rolls = [ModdedRoll(r) for r in roll_strings]
                    if modded_rolls[0].die_type == modded_rolls[1].die_type:
                        raise RollSyntaxError('Opposing rolls cannot have same color')
                    elif modded_rolls[0].die_type == DieType.attack:
                        roll = VsRoll(modded_rolls[0], modded_rolls[1])
                    else:
                        roll = VsRoll(modded_rolls[1], modded_rolls[0])
                else:
                    roll = ModdedRoll(query)
                return self.print_roll(roll)
            except RollSyntaxError as err:
                return [err.__str__(), 'Type `/roll syntax` for help']

    def print_roll(self, roll):
        output = [roll.actual_roll()]
        if roll.calculator_safe():
            roll.calculate_expected()
            link_string = self.formatter.link(roll.calculator_url, roll.calculator_url_description)
            result_string = self.formatter.bold(f'{roll.calculator_result:.3f}')
            output.append(f'{link_string} {result_string}')
        return output

    @staticmethod
    def roll_syntax():
        output = [
            'To roll dice, type `/roll` followed by the number and color of dice. You may include comma-separated dice mods.',
            'e.g.: `/roll 3 red with lock, 1 calculate`', 'You may also roll both red and green dice using `vs`.',
            'e.g.: `/roll 2 red with focus vs 3 green with calc and evade`',
            'Supported mods are: focus, lock, calculate, force, re-roll, evade, reinforce',
            'You can also roll a die `/roll d10` or choose a scenario with `/roll scenario`']
        return output

    @staticmethod
    def roll_numeric(match):
        output = []
        try:
            die_max = match.group('num')
            output.append(str(random.randint(1,int(die_max))))
        except RollSyntaxError as err:
            return [[err.__str__(), 'Type `/roll syntax` for help']]
        return output

    @staticmethod
    def roll_scenario():
        output = []
        scenarios = [
            'Probing Problem',
            'Sabotage',
            'Escort',
            'VIP',
            'Emplacements',
            'Holocron',
            'Contraband',
            'Hyperspace Telemetry',
            'Black Box',
        ]
        output.append(random.choice(scenarios))
        return output


def setup(bot): # this is called by Pycord to set up the cog
    bot.add_cog(DiceRollerCog(bot)) # add the cog to the bot

class RollSyntaxError(Exception):
    pass

