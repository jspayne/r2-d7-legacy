import os
import re
from urllib.parse import quote
from r2d7.DiscordR3.discord_emoji import DiscordEmoji


#DISCORD_EMOJI_JSON = os.path.join(os.path.dirname(__file__), '..', '..', 'icons', 'discord_emoji_id.json')
DISCORD_EMOJI_JSON = os.path.join(os.path.dirname(__file__), '..', '..', 'icons', 'discord_emoji_id_test.json')

class DiscordFormatter(object):
    def __init__(self):
        self.emoji = DiscordEmoji(DISCORD_EMOJI_JSON)
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

