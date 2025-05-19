import json


class DiscordEmoji(object):
    LOOKUP_CONVERT = {
        'criticalhit': 'crit',
        'force': 'purpleforcecharge',
        'koiogranturn': 'kturn'
    }
    LOOKUP_NO_ART = {
        'victory': '[victory]',
        'energy': '[energy]',
        'ordnance': '[ordnance]',
        'hyperdrive': '[hyperdrive]',
        'hugebase': '[hugebase]',
        'magentaenergy': '[magentaenergy]',
        'remote': '[remote]'
    }
    def __init__(self, json_path):
        self.emoji_map = self.LOOKUP_NO_ART.copy()
        self.emoji_data = {}
        with open(json_path) as json_file:
            json_data = json.load(json_file)
        for e in json_data['items']:
            self.emoji_data[e['name']] = e
            self.emoji_map[e['name']] = self._format_emoji(e['name'], e['id'])
        for data_name, discord_name in self.LOOKUP_CONVERT.items():
            self.emoji_map[data_name] = self.emoji_map[discord_name]


    @staticmethod
    def _format_emoji(name, id):
        return f'<:{name}:{id}>'

