import copy
import json
import logging
import os
import re
import urllib.parse as url_parse
from urllib.parse import quote

import requests
from thefuzz import fuzz

from r2d7.DiscordR3.discord_formatter import DiscordFormatter

logger = logging.getLogger(__name__)

JSON_MANIFEST = 'http://localhost:8000/xwing-data2-legacy/data/manifest.json'


# noinspection SpellCheckingInspection
class XwingDB(object):
    def __init__(self, json_manifest=JSON_MANIFEST):
        # Set up json access based on the manifest
        # this will support an http remote access or local filesystem
        # depending on what kind of path is passed to __init__
        self.json_manifest = json_manifest
        url = url_parse.urlparse(json_manifest)
        if url.scheme in ('http', 'https'):
            base_dir = url.path.split('/')
            base_dir = '/'.join(base_dir[1:-2]) # drop filename & data dir
            base_url = url._replace(path=base_dir)
            self._base_url = str(url_parse.urlunparse(base_url)) + '/'
            self._base_path = None
        else:
            self._base_url = None
            self._base_path = os.path.abspath(os.path.join(os.path.dirname(json_manifest), '..'))
        # Load up the reference dicts - not sure if we'll need these
        manifest = self._get_json(json_manifest)[0]
        self.version = manifest['version']
        factions = self._get_json(manifest['factions'])
        self.factions = {faction['xws']: faction for faction in factions}
        stats = self._get_json(manifest['stats'])
        self.stats = {stat['name']: stat for stat in stats}
        actions = self._get_json(manifest['actions'])
        self.actions = {action['name']: action for action in actions}
        # Load up cards
        damage_cards = self._get_json(manifest['damagedecks'])[0]['cards']  # Because stupid
        # Hard code the deck for now - the current data doesn't have the epic damage cards
        self.damage_deck = {dcard['title']: Damage(dcard, self, "core") for dcard in damage_cards}
        jships = []
        for faction in manifest['pilots']:
            jships.extend(self._get_json(faction['ships']))
        self.ships = {ship['name']: Ship(ship, self) for ship in jships}
        self.ships_xws_index = {ship.xws: ship for ship in self.ships.values()}
        self.pilots_xws_index = {}
        for ship in self.ships.values():
            self.pilots_xws_index.update({pilot.xws: pilot for pilot in ship.pilots.values()})
        # Add ship references to each faction
        for faction, fdata in self.factions.items():
            fdata['ships'] = {}
            for ship, sdata in self.ships.items():
                if fdata['xws'] == sdata.faction:
                    self.factions[faction]['ships'][ship] = sdata
        upgrades = []
        for upgrade_type in manifest['upgrades']:
            upgrades.extend(self._get_json(upgrade_type))
        self.upgrades_xws_index = {upgrade['xws']: Upgrade(upgrade, self) for upgrade in upgrades}
        conditions = self._get_json(manifest['conditions'])
        self.conditions = {condition['name']: Condition(condition, self) for condition in conditions}
        self.conditions_xws_index = {condition.xws: condition for condition in self.conditions.values()}
        self.cards = {}
        self.cards.update({p.unique_name: p for p in self.pilots_xws_index.values()})
        self.cards.update({u.unique_name: u for u in self.upgrades_xws_index.values()})
        self.cards.update({c.unique_name: c for c in self.conditions_xws_index.values()})
        self.cards.update({s.unique_name: s for s in self.ships_xws_index.values()})
        self.search_db = {}
        self.search_db.update({p.unique_name: p.search_text for p in self.pilots_xws_index.values()})
        self.search_db.update({u.unique_name: u.search_text for u in self.upgrades_xws_index.values()})
        self.search_db.update({c.unique_name: c.search_text for c in self.conditions_xws_index.values()})
        self.search_db.update({s.unique_name: s.search_text for s in self.ships_xws_index.values()})
        pass

    def _get_json(self, json_paths):
        ret = []
        if isinstance(json_paths, str):
            json_paths = [json_paths]
        for json_path in json_paths:
            if self._base_url:  # fetch json on the web
                jpath = url_parse.urljoin(self._base_url, json_path)
                try:
                    response = requests.get(jpath)
                    response.raise_for_status()
                    response_data = response.json()
                    if isinstance(response_data, dict):
                        ret.append(response.json())
                    else: # it is a list
                        ret.extend(response_data)
                except requests.exceptions.RequestException as e:
                    logger.error(f'Failure fetching JSON from URL: {e}')
            else:  # fetch json from file path
                with open(os.path.join(self._base_path, json_path)) as f:
                    ret.append(json.load(f))
        return ret

    def update_data(self):
        new_version = self._get_json(self.json_manifest)[0]['version']
        if new_version != self.version:
            self.__init__()

    def search_cards(self, search_str):
        results = []
        results_100 = []
        for card in self.cards.values():
            ratio = fuzz.partial_token_set_ratio(search_str, card.search_text)
            if ratio >= 68:
                results.append((card, ratio))
                if ratio == 100:
                    results_100.append((card, ratio))
        if len(results_100):
            results = results_100
        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:10]
        results = [result[0] for result in results]
        return results

# This class can be re-declared with a generic formatter
# I'm only developing for Discord at this time, but I'm keeping
# the Discord specific code separate for future compatibility
class CardData(DiscordFormatter):
    RE_ICON = re.compile(r'(\[([a-zA-Z0-9 ]+)])')  # Search for icon replacement text
    RE_MANEUVER = re.compile(r'(\[([0-9]+)\s+\[([a-zA-Z0-9]+)]])')  # Maneuvers use nested replacements
    RESTRICTION_FACTION_MAP = {
        'galacticempire': 'Imperial',
        'rebelalliance': 'Rebel',
        'scumandvillainy': 'Scum',
        'separatistalliance': 'Separatist',
        'galacticrepublic': 'Republic',
        'firstorder': 'First Order',
        'resistance': 'Resistance'
    }
    STAT_COLORS = {
        "attack": "red",
        "agility": "green",
        "hull": "yellow",
        "shield": "blue",
        "charge": "orange",
        "forcecharge": "purple",
        "initiative": "initiative",
        "energy": "magenta"
    }
    ICON_SUBSTITUTIONS = {
        "stationary": "stop",
    }

    def __init__(self, card_data, db):
        super().__init__()
        self.__dict__.update(card_data)
        self.db = db
        try:
            if self.text:
                self.token_text = self._icon_format_string(self.text)
            if self.ability:
                self.token_ability = self._icon_format_string(self.ability)
                self.token_ability = self.token_ability.replace('Setup:', f'{self.bold("Setup:")}')
        except KeyError:
            pass  # This is a card that has the text on both sides

    def __getattribute__(self, item):
        try:
            return super().__getattribute__(item)
        except AttributeError:
            if item in self.__dict__:
                return self.__dict__[item]
            else:
                return None

    def _icon_format_string(self, text):
        if text is None:
            return None
        # Put icon/emoji placeholders in the text
        out = text
        for m in self.RE_MANEUVER.findall(text):
            slug = "".join(m[2].lower().split())
            slug = self.ICON_SUBSTITUTIONS.get(slug, slug)
            out = out.replace(m[0], f'[{m[1]} {{{slug}}}]')
        for m in self.RE_ICON.findall(text):
            slug = "".join(m[1].lower().split())
            slug = self.ICON_SUBSTITUTIONS.get(slug, slug)
            out = out.replace(m[0], f'{{{slug}}}' )
        return out

    def _bold_card_names(self, text):
        out = text
        for key, pilot in self.db.pilots_xws_index.items():
            out = out.replace(pilot.name, self.bold(pilot.name))
        for title in self.db.conditions.keys():
            out = out.replace(title, self.bold(title))
        return out

    def _format_name(self, card_name):
        return self.wiki_link(card_name)

    @property
    def unique_name(self):
        # Use % for first delimiter so we can quickly extract the xws for lookup later
        return self.xws + '%' + self.name.lower().replace(' ', '_') + '-' + self.__class__.__name__.lower()

    @staticmethod
    def iconify(icon):
        # This function is for compatibility with legacy print methods
        return f"{{{''.join(icon.lower().split())}}}"

    def print_header(self, no_links=False):
        # icon is card specific, add it in the override
        out = ''
        if self.limited:
            out += f'{("•" * self.limited)} '
        if no_links:
            out += self.name
        else:
            out += self.formatted_name
        if self.caption:
            out += f': {self.italics(self.caption)}'
        out += f' {self.print_cost()} {self.print_mode()}\n'
        return out


    def print_action(self, action):
        difficulty = '' if action.get('difficulty', 'White') == 'White' else action['difficulty']
        out = self.iconify(difficulty + action['type'])
        if 'linked' in action:
            out += self.iconify('linked') + self.print_action(action['linked'])
        return out

    def print_stat(self, stat):
        stat_type = stat['type']
        if stat['type'] == 'shields':
            stat_type = 'shield'
        colour = self.STAT_COLORS[stat_type]
        if stat_type == 'attack':
            out = self.iconify(f"red{stat['arc']}")
        else:
            out = self.iconify(f"{colour}{stat_type}")
        plus = 'plus' if stat.get('plus', False) else ''
        recurring = ''
        if stat.get("recovers"):
            recover_amount: int = stat.get("recovers")
            recurring = f"recurring{recover_amount if recover_amount > 1 else ''}"
            if recover_amount < 0:  # Vult Skerris
                recurring = f"losing"
        out += self.iconify(f"{stat_type}{plus}{stat['value']}{recurring}")
        return out

    def print_charge(self, charge, force=False, plus=False):
        if charge is None:
            return None
        charge['type'] = 'forcecharge' if force else 'charge'
        charge['plus'] = plus
        return self.print_stat(charge)

    def print_restrictions(self, restrictions):
        if not restrictions:
            return ''
        ands = []
        for restrict in restrictions:
            ors = []
            if 'action' in restrict:
                ors.append(self.print_action(restrict['action']))
            if 'factions' in restrict:
                ors += [self.RESTRICTION_FACTION_MAP[faction]
                        for faction in restrict['factions']]
            if 'ships' in restrict:
                ors += [self.db.ships_xws_index[ship].name
                        for ship in restrict['ships']]
            if 'sizes' in restrict:
                ors.append(' or '.join(restrict['sizes']) + ' ship')
            if 'names' in restrict:
                ors.append(
                    f"squad including {' or '.join(restrict['names'])}")
            if 'arcs' in restrict:
                ors += [self.iconify(arc) for arc in restrict['arcs']]
            if restrict.get('solitary', False):
                ors.append('Solitary')
            if restrict.get('non-limited', False):
                ors.append('Non-Limited')
            if 'equipped' in restrict:
                ors.append(
                    f"Equipped {''.join(self.iconify(slot) for slot in restrict['equipped'])}")
            if 'force_side' in restrict:
                ors += [f"{side.capitalize()} side" for side in restrict['force_side']]
            if 'standardized' in restrict:
                ors.append('standardized')
            if 'shipAbility' in restrict:
                ors += [f"{ability.title()}" for ability in restrict['shipAbility']]
            if 'keywords' in restrict:
                ors.extend(restrict['keywords'])
            if ors:
                ands.append(' or '.join(ors))
        if ands:
            return self.italics('Restrictions: ' + ', '.join(ands))
        return None

    def print_cost(self):
        try:
            if 'variable' in self.cost:
                out = ''
                if self.cost['variable'] == 'shields':
                    self.cost['variable'] = 'shield'
                if self.cost['variable'] in self.STAT_COLORS.keys():
                    if self.cost['variable'] != self.STAT_COLORS[self.cost['variable']]:
                        out += self.iconify(
                            f"{self.STAT_COLORS[self.cost['variable']]}{self.cost['variable']}")
                    icons = [self.iconify(f"{self.cost['variable']}{stat}")
                            for stat in self.cost['values'].keys()]
                elif self.cost['variable'] == 'size':
                    icons = [self.iconify(f"{size}base")
                            for size in self.cost['values'].keys()]
                else:
                    logger.warning(f"Unrecognised cost variable: {self.cost['variable']}")
                    icons = ['?'] * len(self.cost['values'])
                out += ''.join(
                    f"{icon}{cost}" for icon, cost in zip(icons, self.cost['values'].values()))
            else:
                out = self.cost['value']
        except TypeError:
            out = self.cost
        return f"[{out}]"

    def print_keywords(self):
        if (keywords := self.keywords) is None:
            return ''
        return f"{', '.join(keywords)}"

    def print_grants(self, side):
        if (grants := side.grants) is None:
            return None
        out = ''
        for grant in grants:
            if grant['type'] == 'slot':
                continue
            elif grant['type'] == 'action':
                out += self.print_action(grant['value']) * grant.get('amount', 1)
            elif grant['type'] == 'stat':
                stat = 'shield' if grant['value'] == 'shields' else grant['value']
                symbol = 'minus' if grant['amount'] < 0 else 'plus'
                out += self.iconify(f"{self.STAT_COLORS[stat]}{stat}")
                out += self.iconify(f"{stat}{symbol}{abs(grant['amount'])}")
        return out if out else None

    def print_mode(self):
        out = ''
        if self.standard:
            out = "[Standard]"
        elif self.wildspace:
            out = "[Wild Space]"
        elif self.epic:
            out += "[Epic]"
        return out

    def print_attack(self, side):
        if (atk := side.attack) is None:
            return None
        if atk['minrange'] != atk['maxrange']:
            ranges = f"{atk['minrange']}-{atk['maxrange']}"
        else:
            ranges = str(atk['minrange'])
        return (
            self.iconify('red' + atk['arc']) +
            self.iconify(f"attack{atk['value']}") +
            (self.iconify('redrangebonusindicator')
                if atk.get('ordnance', False) else '') +
            ranges
        )

    def print_device(self, device):
        return f"{self.bold(device['name'])} ({device['type']})" + device['effect']

    def print_body(self, side):
        out =  ''
        if self.restrictions:
            out += self.print_restrictions(self.restrictions) + '\n'
        if side.token_ability:
            out += f'{self._bold_card_names(side.token_ability)}\n'
        if side.text:
            out += f'{self.italics(self.text)}\n'
        return out

    def print_last(self, side):
        last_line = [self.print_attack(side),
                     self.print_charge(side.charge),
                     self.print_charge(side.force, force=True, plus=True),
                     self.print_grants(side)]
        last_line = list(filter(None, last_line))
        if last_line:
            return ' | '.join(last_line)
        else:
            return ''

    def wiki_link(self, card_name, crew_of_pilot=False, wiki_name=False):
        if not wiki_name:
            wiki_name = card_name
        fudged_name = re.sub(r' ', '_', wiki_name)
        # Data and the wiki use different name conventions
        #TODO work out the fudges for xwing-data
        # fudged_name = re.sub(r'\(Scum\)', '(S&V)', fudged_name)
        # fudged_name = re.sub(r'\((PS9|TFA)\)', '(HOR)', fudged_name)
        if 'Core Set' in card_name:
            fudged_name = 'X-Wing_' + fudged_name
        fudged_name = re.sub(r'-wing', '-Wing', fudged_name)
        fudged_name = re.sub(r'/V', '/v', fudged_name)
        fudged_name = re.sub(r'/X', '/x', fudged_name)
        fudged_name = re.sub(r'_\([-+]1\)', '', fudged_name)
        if crew_of_pilot:
            fudged_name += '_(Crew)'
        # Stupid Nien Nunb is a stupid special case
        elif fudged_name == 'Nien_Nunb':
            fudged_name += '_(T-70_X-Wing)'
        # All Hera's are suffixed on the wiki
        elif fudged_name == 'Hera_Syndulla':
            fudged_name += '_(VCX-100)'
        elif re.match(r'"Heavy_Scyk"_Interceptor', fudged_name):
            fudged_name = '"Heavy_Scyk"_Interceptor'
        fudged_name = fudged_name.replace('“', '').replace('”', '')
        fudged_name = quote(fudged_name)
        url = f"https://xwingtmgwiki.com/{fudged_name}"
        if self.text is not None:
            tip = self.text
        else:
            tip = self.ability
        return self.link(url, card_name, tooltip=tip)

    @property
    def search_text(self):
        out = ''
        out += self.__dict__.get('name', '') + ' '
        out += self.__dict__.get('ability', '') + ' '
        if self.shipAbility:
            out += f'{self.shipAbility["name"]} {self.shipAbility["text"]}'
        out += ' '.join(self.__dict__.get('keywords', []))
        out += ' '.join(self.__dict__.get('nicknames', []))
        return out

class Card(CardData):
    # A card is made of one or more sides
    def __init__(self, card_data, db):
        super().__init__(card_data, db)
        if sides := card_data.pop('sides', None):
            self.sides = [Side(side, db) for side in sides]
        else:
            self.formatted_name = self._format_name(card_data.get('name', card_data.get('title', None))) # Sometimes the name and text are on the side
        return

class Side(CardData):
    def __init__(self, side_data, db):
        super().__init__(side_data, db)
        self.formatted_name = self._format_name(side_data.get('name', side_data.get('title', None)))
        return

class Upgrade(Card):
    def __init__(self, card_data, db):
        super().__init__(card_data, db)
        if self.shipAbility:
            self.token_ship_ability = (f'{self.bold(self.shipAbility["name"])}: '
                                       f'{self._icon_format_string(self.shipAbility["text"])}\n')
        return

    def __str__(self):
        out = ''
        for side in self.sides or [self]:
            out += f'{self._icon_format_string(f"[{side.type}]")}' # upgrade icon
            if side.limited:
                out += f' {"•" * side.limited} '
            out += f'{side.formatted_name} {self.print_cost()} {self.print_mode()}\n'
            out += self.print_keywords()
            out += self.print_body(side)
            out += side.token_ship_ability or ''  # some Config cards have replacement Ship Abilities
            out += self.print_last(side)

            if side.device:
                if side.device['type'] == 'Remote':
                    side.device['category'] = 'Remote'
                    side.device['ability'] = side.device.get('effect', None)
                    out += str(Upgrade(side.device, self.db))
                else:
                    out += self.print_device(side.device)

                for condition in side.conditions or []:
                    out += str(self.db.conditions_xws_index[condition])

        out = out.format_map(self.emoji_map)
        return out

    def print_header(self, no_links=False):
        return f'{self._icon_format_string(f"[{self.sides[0].type}]")} ' + super().print_header(no_links=no_links)

    @property
    def unique_name(self):
        # Use % for first delimiter so we can quickly extract the xws for lookup later
        return self.xws + '%' + self.name.lower().replace(' ', '_') + '-' + self.sides[0].type.lower()

    @property
    def search_text(self):
        out = ''
        out += self.__dict__.get('name', '') + ' '
        out += ' '.join(self.__dict__.get('nicknames', []))
        out += self.__dict__.get('caption', '') + ' '
        for side in self.sides:
            out += side.__dict__.get('title', '') + ' '
            out += side.__dict__.get('ability', '') + ' '
        return out


class Pilot(Card):
    def __init__(self, card_data, db, ship):
        if card_data.get('sides', None):
            raise NotImplementedError('Pilot cards should only have one side.')
        super().__init__(card_data, db)
        self.ship = ship
        # Oddly, the ship specific ability is defined per pilot - some
        # ships (e.g. Sep Vulture) have different ship abilities depending
        # on the pilot
        if self.shipAbility:
            self.token_ship_ability = (f'{self.bold(self.shipAbility["name"])}: '
                                       f'{self._icon_format_string(self.shipAbility["text"])}\n')
        return

    def __str__(self):
        out = self.print_header()
        out += self.print_body(self)
        out += self.token_ship_ability or ''
        out += self.print_keywords()
        out += self.print_last(self)
        for condition in self.conditions or []:
            out += str(self.db.conditions_xws_index[condition])
        out = out.format_map(self.emoji_map)
        return out

    def print_header(self, no_links=False):
        out = f'{self.iconify(self.ship.xws)} ' + super().print_header(no_links=no_links)
        return out

class Ship(CardData):
    # TODO: str method
    def __init__(self, card_data, db):
        super().__init__(card_data, db)
        self.faction = None
        pilots = copy.deepcopy(card_data['pilots'])
        del card_data['pilots']
        self.__dict__.update(card_data)
        self.pilots = {pilot['name']: Pilot(pilot, db, self) for pilot in pilots}
        return

class Damage(Card):
    def __init__(self, card_data, db, deck):
        if card_data.get('sides', None):
            raise NotImplementedError('Damage cards should only have one side.')
        super().__init__(card_data, db)
        self.deck = deck
        return

    def __str__(self):
        out = f'{{atkcrit}} {self.bold(self.title)} ({self.deck}) {"•" * self.amount}\n'
        out += f'{self.token_text}\n'
        out = out.replace('Action:', f'\n{self.bold("Action:")}')
        out = out.format_map(self.emoji_map)
        return out

    def _format_name(self, card_name):
        # This card type doesn't have a wiki link
        return self.bold(card_name)

class Condition(Card):
    def __init__(self, card_data, db):
        if card_data.get('sides', None):
            raise NotImplementedError('Condition cards should only have one side.')
        super().__init__(card_data, db)
        return

    def __str__(self):
        out = f'{{condition}} • {self.bold(self.name)}\n'
        out += f'{self._bold_card_names(self.token_ability)}\n'
        out = out.format_map(self.emoji_map)
        return out

    def _format_name(self, card_name):
        # This card type doesn't have a wiki link
        return self.bold(card_name)

class SearchString(object):
    def __init__(self, search_string):
        self.search_text = search_string

def main():
    logger.setLevel(logging.DEBUG)
    db = XwingDB()
    # for name in db.damage_deck.keys():
    #     print(str(db.damage_deck[name]) + '\n')
    # for name in db.conditions.keys():
    #     print(str(db.conditions[name]) + '\n')
    for xws in db.upgrades_xws_index.keys():
        print(str(db.upgrades_xws_index[xws]) + '\n')
    foo = db.search_cards('sabine')
    pass


if __name__ == '__main__':
    main()

