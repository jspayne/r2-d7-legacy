import json


class DiscordEmoji(object):
    def __init__(self, json_path):
        self.emoji_map = {}
        with open(json_path) as json_file:
            json_data = json.load(json_file)
        for e in json_data['items']:
            self.emoji_map[e['name']] = e['id']

    def __getitem__(self, item):
        try:
            return f'<:{item}:{self.emoji_map[item]}>'
        except KeyError:
            return f'<:{item}:>'
