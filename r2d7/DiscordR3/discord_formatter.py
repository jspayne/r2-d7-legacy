import discord
import os
from threading import Lock
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

    def __init__(self):
        self.emoji = None
        self.emoji_map = {}
        self.lock = Lock()

    def set_bot(self, bot):
        """
        This object setup is probably more complex than it needs to be,
        but I couldn't come up with a better way.

        * The object should be global because the emoji map is fairly large,
          and we don't want to pull it for every cog.
        * I tried creating a global that was initialized by __main__, but importing
          a variable doesn't really make it a writeable global.
        * The global DiscordFormatter is then declared in __init__, but it can't
          initialize the emoji map because there isn't a global reference to bot.
        * Even if there were a bot global, it isn't fully initialized at __main__,
          let alone __init__.

        This function works around this by setting the bot at cog startup,
        and going ahead with setting up the emoji map at that time.
        The check of self.emoji ensures that this setup only runs once.
        It should be called by the setup of every cog so that if cogs are removed/added
        it will still work.  There is also a very small possibility of one cog
        getting a command before the one doing the initialization finishes.

        I'm not sure if pycord runs cogs in separate threads, but we'll lock this
        setup just in case to avoid race conditions.
        """
        self.lock.acquire()
        if self.emoji is None:
            if bot is None:
                self.emoji = DiscordEmoji(DISCORD_EMOJI_JSON)
                self.emoji_map = self.emoji.emoji_map
            else:
                self.emoji_map = DiscordNativeEmoji(bot)
        self.lock.release()

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

discord_formatter = DiscordFormatter()