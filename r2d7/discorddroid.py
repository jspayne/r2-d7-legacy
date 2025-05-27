from r2d7.slackdroid import SlackDroid
import re
import os
from r2d7.emoji import DiscordEmoji
class DiscordDroid(SlackDroid):
    """
    Discord is similar enough to Slack that we subclass that and then modify.
    """
    def __init__(self):
        super().__init__()
        self.emoji_map = DiscordEmoji(
            os.path.join(os.path.dirname(__file__), '..', 'icons', 'discord_emoji_id.json'))

    @staticmethod
    def bold(text):
        return f"**{text}**"

    @staticmethod
    def italics(text):
        return f"*{text}*"

    @staticmethod
    def link(url, name, tooltip=None):
        if tooltip:
            return f'[{name}]({url} "{tooltip}")'
        else:
            return f"[{name}]({url})"

    def iconify(self, name, special_chars=False):
        name = name.lower()
        if special_chars:
            name = re.sub(r'[^a-zA-Z0-9\-\_]', '', name)
        else:
            name = re.sub(r'[^a-zA-Z0-9]', '', name)
        name = name.replace('+', 'plus')
        if name in ['bomb', 'shield']:
            name = 'x' + name
        # Lock is a standard emoji, so we'll stick with targetlock for 2.0
        elif name == 'lock':
            name = 'targetlock'
        elif name == 'rebelalliance':
            name = 'rebel'
        elif name == 'scumandvillainy':
            name = 'scum'
        elif name == 'galacticempire':
            name = 'imperial'
        elif name == 'firstorder':
            name = 'first_order'
        # elif name == 'delta7baethersprite':
        #     name = 'delta7aethersprite'
        return self.emoji_map[name]
