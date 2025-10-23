import discord
import os
from r2d7.DiscordR3.discord_emoji import DiscordEmoji, DiscordNativeEmoji



#DISCORD_EMOJI_JSON = os.path.join(os.path.dirname(__file__), '..', '..', 'icons', 'discord_emoji_id.json')
DISCORD_EMOJI_JSON = os.path.join(os.path.dirname(__file__), '..', '..', 'icons', 'discord_emoji_id_test.json')

class DiscordFormatter(object):
    FACTION_COLORS = {
        "rebelalliance": "0xcb120e",
        "galacticempire": "0xd6d6dd",
        "scumandvillainy": "0x253a21",
        "firstorder": "0xb42828",
        "resistance": "0xd87325",
        "galacticrepublic": "0xeff3f3",
        "separatistalliance": "0x20308d",
    }

    def __init__(self, bot=None):
        if bot is None:
            self.emoji = DiscordEmoji(DISCORD_EMOJI_JSON)
        else:
            self.emoji = DiscordNativeEmoji(bot)
        self.emoji_map = self.emoji.emoji_map

    @staticmethod
    def bold(text):
        if text:
            return f"**{text}**"
        else:
            return ""

    @staticmethod
    def italics(text):
        if text:
            return f"*{text}*"
        else:
            return ""

    @staticmethod
    def link(url, name, tooltip=None):
        if tooltip:
            return f'[{name}]({url} "{tooltip}")'
        else:
            return f"[{name}]({url})"

    @staticmethod
    def _discord_color(hex_color):
        if isinstance(hex_color, str):
            hex_color = int(hex_color, 16)
        return discord.Colour(hex_color)

    def get_faction_color(self, faction_id):
        return self._discord_color(self.FACTION_COLORS.get(faction_id.lower(), "0x000000"))