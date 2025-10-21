import json

"""
This class is used to convert emoji names to their discord server emoji equivalents

This version is a temporary hack until pycord supports pulling the emoji data from the server
"""

class DiscordEmoji(object):
    LOOKUP_CONVERT = {
        'criticalhit': 'crit',
        'force': 'purpleforcecharge',
        'koiogranturn': 'kturn',
        'lock': 'targetlock',
        'rebelalliance': 'rebel',
        'scumandvillainy': 'scum',
        'galacticempire': 'imperial',
        'firstorder': 'first_order',
    }
    LOOKUP_NO_ART = {
        'victory': '[victory]',
        'energy': '[energy]',
        'ordnance': '[ordnance]',
        'hyperdrive': '[hyperdrive]',
        'hugebase': '[hugebase]',
        'magentaenergy': '[magentaenergy]',
        'remote': '[remote]',
        'bomb': '[bomb]',
        'gauntletfighter': '[gauntletfighter]',
        'clonez95headhunter': '[clonez95headhunter]',
        'cr90corelliancorvette': '[cr90corelliancorvette]',
        'rogueclassstarfighter': '[rogueclassstarfighter]',
    }
    def __init__(self, json_path):
        self.emoji_map = {}
        self.emoji_map.update(self.LOOKUP_NO_ART)
        self.emoji_data = {}
        with open(json_path) as json_file:
            json_data = json.load(json_file)
        for e in json_data['items']:
            self.emoji_data[e['name']] = e
            self.emoji_map[e['name']] = self._format_emoji(e['name'], e['id'])
        for data_name, discord_name in self.LOOKUP_CONVERT.items():
            self.emoji_map[data_name] = self.emoji_map[discord_name]


    @staticmethod
    def _format_emoji(name, em_id):
        out = f'<:{name}:{em_id}>'
        return out

