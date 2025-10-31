import json
import time
from logging import getLogger
from threading import Lock
from warnings import deprecated

log = getLogger(__name__)
"""
This class is used to convert emoji names to their discord server emoji equivalents

DiscordEmoji is a hack from before the app emoji API was available in pycord. (deprecated)
DiscordNativeEmoji replaces DiscordEmoji and pulls the emoji map from the server.
"""

LOOKUP_CONVERT = {
    'criticalhit': 'crit',
    'force': 'purpleforcecharge',
    'koiogranturn': 'kturn',
    'lock': 'targetlock',
    'rebelalliance': 'rebel',
    'scumandvillainy': 'scum',
    'galacticempire': 'imperial',
    'firstorder': 'first_order',
    'bomb': 'device',
    'energy': 'recover',
    'magentaenergy': 'redrecover',
    'ordnance': 'redrangebonusindicator'
}
LOOKUP_NO_ART = {
    'victory': '[victory]',
    'hyperdrive': '[hyperdrive]',
    'hugebase': '[hugebase]',
    'remote': '[remote]',
}


class DiscordEmoji(object):
    @deprecated('DiscordNativeEmoji pulls the emoji map from the server')
    def __init__(self, json_path):
        self.emoji_map = {}
        self.emoji_map.update(LOOKUP_NO_ART)
        self.emoji_data = {}
        with open(json_path) as json_file:
            json_data = json.load(json_file)
        for e in json_data['items']:
            self.emoji_data[e['name']] = e
            self.emoji_map[e['name']] = self._format_emoji(e['name'], e['id'])
        for data_name, discord_name in LOOKUP_CONVERT.items():
            self.emoji_map[data_name] = self.emoji_map[discord_name]

    @staticmethod
    def _format_emoji(name, em_id):
        out = f'<:{name}:{em_id}>'
        return out


class DiscordNativeEmoji(object):
    UPDATE_RATE = 600
    def __init__(self, bot):
        self.bot = bot
        self._emoji_map = {}
        self._emoji_map.update(LOOKUP_NO_ART)  # put this first so that if they are added, this is overwritten
        self._emoji_data = {}
        self.last_update = 0
        # bot has to come up fully before we can pull the emoji data,
        # so leave the fetch for the first access
        self.lock = Lock()

    def update_map(self):
        self.lock.acquire() # prevent multiple threads from doing the update simultaneously
        if (time.time() - self.last_update) > self.UPDATE_RATE:
            log.debug('Checking for updated application emoji')
            for emoji in self.bot.app_emojis:
                self._emoji_data[emoji.name] = emoji
                self._emoji_map[emoji.name] = emoji.mention
            for data_name, discord_name in LOOKUP_CONVERT.items():
                self._emoji_map[data_name] = self._emoji_map[discord_name]
            self.last_update = time.time()
        self.lock.release()

    def __getitem__(self, item):
        self.update_map()
        self.lock.acquire() # avoid looking up the emoji if another thread is updating it
        em = self._emoji_map[item]
        self.lock.release()
        return em