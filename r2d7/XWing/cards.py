import copy
import json
import logging
import os
import re
import time
import urllib.parse as url_parse
from collections import defaultdict
from itertools import groupby
from urllib.parse import quote
from r2d7.XWing.legality import CardLegality

import requests
from thefuzz import fuzz

from r2d7.DiscordR3.discord_formatter import DiscordFormatter

logger = logging.getLogger(__name__)

JSON_MANIFEST = 'http://localhost:8000/xwing-data2-legacy/data/manifest.json'


# noinspection SpellCheckingInspection
class XwingDB(object):
    UPDATE_RATE = 600  # seconds
    def __init__(self, json_manifest=JSON_MANIFEST):
        # Set up json access based on the manifest
        # this will support a http remote access or local filesystem
        # depending on what kind of path is passed to __init__
        self.last_update = time.time()
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
        manifest = self.get_json(json_manifest)[0]
        self.version = manifest['version']
        factions = self.get_json(manifest['factions'])
        self.factions = {faction['xws']: faction for faction in factions}
        stats = self.get_json(manifest['stats'])
        self.stats = {stat['name']: stat for stat in stats}
        actions = self.get_json(manifest['actions'])
        self.actions = {action['name']: action for action in actions}
        # Load up cards
        damage_cards = self.get_json(manifest['damagedecks'])[0]['cards']  # Because stupid
        # Hard code the deck for now - the current data doesn't have the epic damage cards
        self.damage_deck = {dcard['title']: Damage(dcard, self, "core") for dcard in damage_cards}
        # Stick the ships in their factions becaue ship xws are not unique between factions
        self.ships = ShipDb(manifest['pilots'], self)
        self.pilots_xws_index = {}
        for faction in self.ships.factions.values():
            for ship in faction.values():
                self.pilots_xws_index.update({pilot.xws: pilot for pilot in ship.pilots.values()})
        upgrades = []
        for upgrade_type in manifest['upgrades']:
            upgrades.extend(self.get_json(upgrade_type))
        self.upgrades_xws_index = {upgrade['xws']: Upgrade(upgrade, self) for upgrade in upgrades}
        conditions = self.get_json(manifest['conditions'])
        self.conditions = {condition['name']: Condition(condition, self) for condition in conditions}
        self.conditions_xws_index = {condition.xws: condition for condition in self.conditions.values()}
        self.cards = []
        self.cards.extend([u for u in self.upgrades_xws_index.values()])
        self.cards.extend([p for p in self.pilots_xws_index.values()])
        self.cards.extend([c for c in self.conditions_xws_index.values()])
        self.cards.extend([d for d in self.damage_deck.values()])
        for ships in self.ships.factions.values():
            self.cards.extend([s for s in ships.values()])
        pass

    def get_json(self, json_paths):
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
        if (time.time() - self.last_update) > self.UPDATE_RATE:
            logger.debug('Checking for updated data')
            new_version = self.get_json(self.json_manifest)[0]['version']
            if new_version != self.version:
                logger.debug(f'Old version: {self.version}, new version: {new_version}.  Updating...')
                self.__init__()

    def search_cards(self, search_str, test=False):
        name_results = []
        name_results_100 = []
        results = []
        results_100 = []
        search_str = search_str.lower().strip()
        for card in self.cards:
            ratio = fuzz.partial_token_sort_ratio(search_str, card.search_text)
            if ratio >= 68:
                results.append((card, ratio))
                if ratio == 100:
                    results_100.append((card, ratio))
            if search_str in card.search_name:  # exact match
                name_results_100.append((card, 100))
            else:
                ratio = fuzz.partial_token_sort_ratio(search_str, card.name)
                if ratio >= 68:
                    name_results.append((card, ratio))
        if len(name_results_100):
            results = name_results_100
        elif len(results_100):
            results = results_100
        elif len(name_results):
            results = name_results
        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:10]
        if not test:
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
        "charge": "yellow",
        "forcecharge": "purple",
        "initiative": "orange",
        "energy": "magenta"
    }
    ICON_SUBSTITUTIONS = {
        "stationary": "stop",
    }
    ARC_ICONS = {
        'Turret': 'turret',
        'Auxiliary Rear': 'frontback',
        'Auxiliary 180': '180',
        'Bullseye': 'bullseye',
    }
    def __init__(self, card_data, db):
        super().__init__()
        self.__dict__.update(card_data)
        self.db = db
        self.legality = CardLegality(card_data)
        if self.text:
            self.token_text = self._icon_format_string(self.text)
        if self.ability:
            self.token_ability = self._icon_format_string(self.ability)
            for key in ['Setup:', 'Action:']:
                self.token_ability = self.token_ability.replace(key, '\n' + f'{self.bold(key)}')

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
        ret = self.xws + '%'
        ret += self.name.lower().replace(' ', '_')
        return ret

    @staticmethod
    def iconify(name, special_chars=False):
        name = name.lower()
        if special_chars:
            name = re.sub(r'[^a-zA-Z0-9\-_]', '', name)
        else:
            name = re.sub(r'[^a-zA-Z0-9]', '', name)
        name = name.replace('+', 'plus')
        out = f'{{{name}}}'
        return out

    def get_image(self):
        return self.image  # Returns None if there is no image at this level

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
        out += self.print_restrictions() + '\n'
        return out

    def select_line(self):
            out = {'label': f'{("•" * self.limited)} {self.name or self.title}'}
            return out

    def print_ship_stats(self):
        # generates a single line of stat icons for a pilot or ship card
        if self.ship:  # This is a pilot card
            ship = self.ship
            pilot = self
        else:
            ship = self
            pilot = None

        line = []
        stats = [self.iconify(ship.faction)]
        if pilot:
            stats.append(self.iconify(f"initiative{pilot.initiative}"))
            if pilot.engagement in (0, 1):
                stats.append(self.iconify(f"engagement{pilot.engagement}"))
        for stat in ship.stats:
            stats.append(self.print_stat(stat))
        if pilot and pilot.charges:
            stats.append(self.print_charge(pilot.charges))
        if pilot and pilot.force:
            stats.append(self.print_charge(pilot.force, force=True))
        line.append(''.join(stats))

        if pilot and pilot.shipActions:
            line.append('|'.join(
                self.print_action(action) for action in pilot.shipActions
            ))
        elif ship.actions:
            line.append('|'.join(
                self.print_action(action) for action in ship.actions
            ))

        if not pilot and ship.slots:
            line.append(''.join(self.iconify(slot) for slot in ship.slots))

        if pilot and pilot.slots:
            line.append(''.join(self.iconify(slot) for slot in pilot.slots))

        return '\n'.join(line) + '\n'


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

    def print_restrictions(self):
        if not self.restrictions:
            return ''
        ands = []
        ors = []

        if 'action' in self.restrictions:
            ors.append(self.print_action(self.restrictions['action']))
        if 'factions' in self.restrictions:
            ors += [self.RESTRICTION_FACTION_MAP[faction]
                    for faction in self.restrictions['factions']]
        if 'ships' in self.restrictions:
            for ship_xws in self.restrictions['ships']:
                ship = self.db.ships[ship_xws]
                if isinstance(ship, list):
                    ors.append(ship[0].name)  # Ships that have clashing XWS have the same name
                else:
                    ors.append(ship.name)
        if 'sizes' in self.restrictions:
            ors.append(' or '.join(self.restrictions['sizes']) + ' ship')
        if 'names' in self.restrictions:
            ors.append(
                f"squad including {' or '.join(self.restrictions['names'])}")
        if 'arcs' in self.restrictions:
            ors += [self.iconify(arc) for arc in self.restrictions['arcs']]
        if self.restrictions.get('solitary', False):
            ors.append('Solitary')
        if self.restrictions.get('non-limited', False):
            ors.append('Non-Limited')
        if 'equipped' in self.restrictions:
            ors.append(
                f"Equipped {''.join(self.iconify(slot) for slot in self.restrictions['equipped'])}")
        if 'force_side' in self.restrictions:
            ors += [f"{side.capitalize()} side" for side in self.restrictions['force_side']]
        if 'standardized' in self.restrictions:
            ors.append('standardized')
        if 'shipAbility' in self.restrictions:
            ors += [f"{ability.title()}" for ability in self.restrictions['shipAbility']]
        if 'keywords' in self.restrictions:
            ors.extend(self.restrictions['keywords'])

        if ors:
            ands.append(' or '.join(ors))

        if ands:
            return self.italics('Restrictions: ' + ', '.join(ands))
        return None

    def get_cost(self):
        return self.cost

    def print_cost(self):
        return f"[{self.get_cost()}]"

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
            ranges + '\n'
        )

    def print_device(self, device):
        return f"{self.bold(device['name'])} ({device['type']})" + device['effect']

    def print_body(self):
        out =  ''
        if self.token_ability:
            out += f'{self._bold_card_names(self.token_ability)}\n'
        if self.text:
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
        out += self.__dict__.get('xws', '') + ' '
        out += self.__dict__.get('ability', '') + ' '
        if self.shipAbility:
            out += f'{self.shipAbility["name"]} {self.shipAbility["text"]} '
        out += ' '.join(self.__dict__.get('keywords', [])) + ' '
        out += ' '.join(self.__dict__.get('nicknames', []))
        return out

    @property
    def search_name(self):
        out = ''
        out += self.__dict__.get('name', '') + ' '
        for side in self.__dict__.get('sides', []):
            if side.title:
                out += side.title + ' '
        out += ' '.join(self.__dict__.get('nicknames', []))
        return out.lower().strip()

class Card(CardData):
    # A card is made of one or more sides
    def __init__(self, card_data, db):
        super().__init__(card_data, db)
        self.formatted_name = self._format_name(card_data.get('name', card_data.get('title', None))) # Sometimes the name and text are on the side
        return

class Side(CardData):
    def __init__(self, side_data, db):
        super().__init__(side_data, db)
        self.formatted_name = self._format_name(side_data.get('name', side_data.get('title', None)))
        return

class Upgrade(Card):
    def __init__(self, card_data, db):
        restrictions = card_data.get('restrictions', [])
        if len(restrictions):
            del card_data['restrictions']
        super().__init__(card_data, db)
        self.sides = [Side(side, db) for side in card_data['sides']]
        if self.shipAbility:
            self.token_ship_ability = (f'{self.bold(self.shipAbility["name"])}: '
                                       f'{self._icon_format_string(self.shipAbility["text"])}\n')
        self.restrictions = {}
        for restriction in restrictions:
            for key, value in restriction.items():
                self.restrictions[key] = value
        return

    def __str__(self):
        out = self.print_header()
        for side in self.sides:
            if len(self.sides) > 1:
                out += f'{self.bold(side.title)}\n'
            out += self.print_side(side) + '\n'
        out = out.format_map(self.emoji_map)
        return out

    def get_image(self):
        return self.sides[0].get_image()

    def print_cost(self):
        if self.standardLoadoutOnly:
            return '[SL]'
        else:
            return self.print_cost()

    def get_cost(self, pilot=None):
        out = 0
        if 'variable' in self.cost:
            cost_key = self.cost['variable']
            # Check if the variable is a pilot attribute (currently only "initiative")
            cost_index = pilot.__dict__.get(cost_key, None)
            if cost_index is None:
                # Now check direct Ship attributes (currently only "size")
                cost_index = pilot.ship.__dict__.get(cost_key, None)
            if cost_index is None:
                # Now check if it is a ship stat (currently only "agility")
                for stat in pilot.ship.stats:
                    if stat['type'] == cost_key:
                        cost_index = stat['value']
                        break
            if cost_index is None:
                logger.error(f'Unknown cost variable: {cost_key}')
                return 0
            out = self.cost['values'][str(cost_index)]
        else:
            out = self.cost['value']
        return out

    def print_header(self, no_links=False):
        out = f'{self._icon_format_string(f"[{self.sides[0].type}]")} ' + super().print_header(no_links=no_links)
        return out.format_map(self.emoji_map)

    def select_line(self):
        out = super().select_line()
        out['emoji'] = self.iconify(self.sides[0].type).format_map(self.emoji_map)
        if self.standardLoadoutOnly:
            out['label'] += ' (Standard Loadout)'
        if len(self.restrictions.get('factions', [])):
            flist = [ self.db.factions[fkey]['name'] for fkey in self.restrictions["factions"] ]
            out['label'] += f' ({",".join(flist)})'
        out['label'] += f' {self.print_mode()} '
        cost = self.print_cost()
        if '{' in cost:
            out['label'] += f'[Variable]'
        else:
            out['label'] += f'{cost}'
        return out

    def print_side(self, side):
        out = ''
        out += side.print_keywords()
        out += side.print_body()
        out += side.token_ship_ability or ''  # some Config cards have replacement Ship Abilities
        out += self.print_last(side)

        if self.device:
            if self.device['type'] == 'Remote':
                self.device['category'] = 'Remote'
                self.device['ability'] = self.device.get('effect', None)
                out += str(Upgrade(self.device, self.db))
            else:
                out += self.print_device(self.device)

            for condition in self.conditions or []:
                out += str(side.db.conditions_xws_index[condition])

        out = out.format_map(self.emoji_map)
        return out

    @property
    def unique_name(self):
        # Use % for first delimiter so we can quickly extract the xws for lookup later
        ret = super().unique_name + '-'
        ret += self.sides[0].type + '-'
        ret += '-'.join(self.sides[0].slots).lower()
        ret += '-upgrade'
        return ret

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
        out += self.print_ship_stats()
        out += self.print_body()
        out += self.token_ship_ability or ''
        out += self.print_keywords() + '\n'
        out += self.print_last(self)
        for condition in self.conditions or []:
            out += str(self.db.conditions_xws_index[condition])
        out = out.format_map(self.emoji_map)
        return out

    @property
    def unique_name(self):
        ret = super().unique_name + '-'
        ret += self.ship.faction + '-' # e.g. tielnfighter clashes between Imperial & Rebel
        ret += 'pilot'
        return ret

    def select_line(self):
        out = super().select_line()
        out['emoji'] = self.iconify(self.ship.xws).format_map(self.emoji_map)
        out['label'] += f'({self.db.factions[self.ship.faction]["name"]})'
        out['label'] += f' {self.print_mode()} {self.print_cost()}'
        return out

    def pilot_select_line(self):
        # Used when selecting pilots from a ship
        out = {'label': f'{self.name} ',
               'emoji': self.iconify(f'initiative{self.initiative}').format_map(self.emoji_map)}
        if self.limited:
            out['label'] = f'{("•" * self.limited)} {out["label"]}'
        if self.caption:
            out['label'] += f': {self.caption}'
        out['label'] += f' {self.print_cost()}'
        return out

    def print_header(self, no_links=False):
        out = f'{self.iconify(self.ship.xws)} ' + super().print_header(no_links=no_links)
        return out.format_map(self.emoji_map)

    def pilot_line(self):
        out = f'{self.iconify(self.ship.xws)}{self.iconify("initiative" + str(self.initiative))} {self.formatted_name} {self.print_cost()}'
        return out.format_map(self.emoji_map)

class Ship(CardData):
    # Dialgen format defined here: http://xwvassal.info/dialgen/dialgen
    maneuver_key = (
        ('T', 'turnleft'),
        ('B', 'bankleft'),
        ('F', 'straight'),
        ('N', 'bankright'),
        ('Y', 'turnright'),
        ('K', 'kturn'),
        ('L', 'sloopleft'),
        ('P', 'sloopright'),
        ('E', 'trollleft'),
        ('R', 'trollright'),
        ('A', 'reversebankleft'),
        ('S', 'reversestraight'),
        ('D', 'reversebankright'),
    )
    stop_maneuver = ('O', 'stop')

    difficulty_key = {
        'R': 'red',
        'W': '',
        'G': 'green',
        'B': 'blue',
        'P': 'purple'
    }

    def __init__(self, card_data, faction, db):
        super().__init__(card_data, db)
        self.faction = faction
        pilots = copy.deepcopy(card_data['pilots'])
        del card_data['pilots']
        self.__dict__.update(card_data)
        self.pilots = {pilot['xws']: Pilot(pilot, db, self) for pilot in pilots}
        self.formatted_name = self._format_name(card_data['name'])
        return

    @property
    def unique_name(self):
        ret = super().unique_name
        ret += self.faction + '-'  # e.g. tielnfighter clashes between Imperial & Rebel
        # dial codes clash between factions, so adding them doesn't help
        ret += 'ship'
        return ret

    def print_maneuvers(self):
        used_moves = {move[1] for move in self.dial}
        dial = {speed: {move[1]: move[2] for move in moves}
                for speed, moves in groupby(self.dial, lambda move: move[0])}
        result = []
        blank = self.iconify('blank')
        for speed, moves in dial.items():
            line = [f'`{speed}`' + ' ']
            for dialgen_move, droid_move in self.maneuver_key:
                if dialgen_move not in used_moves:
                    continue
                if speed == '0' and dialgen_move == 'F':
                    dialgen_move, droid_move = self.stop_maneuver
                if dialgen_move in moves:
                    line.append(self.iconify(
                        self.difficulty_key[moves[dialgen_move]] + droid_move
                    ))
                else:
                    line.append(blank)
            result.append(''.join(line))
        return list(reversed(result))

    def __str__(self):
        lines = [self.print_header(),
                 self.print_ship_stats(),
                 ]
        lines.extend(self.print_maneuvers())
        out = '\n'.join(lines)
        out = out.format_map(self.emoji_map)
        return out

    def print_header(self, no_links=False):
        items = [f'{self.iconify(self.xws)}',
                 self.formatted_name,
                 self.iconify(f"{self.size.lower()}base")]
        line = ' '.join(items)
        return line.format_map(self.emoji_map)

    def select_line(self):
        # Used when selecting pilots from a direct search
        out = {'label': self.name,
               'emoji': self.iconify(self.xws).format_map(self.emoji_map)}
        out['label'] += f'({self.db.factions[self.faction]["name"]})'
        if self.standardLoadoutOnly:
            out['label'] += ' (Standard Loadout)'
        return out

    def get_grouped_pilots(self):
        pilots = defaultdict(list)
        # Add common options to fix order
        pilots['Standard'] = []
        pilots['Left-Side Legal'] = []
        pilots['Standard Loadout'] = []
        for pilot in self.pilots.values():
            if pilot.standardLoadout:
                group = "Standard Loadout"
            elif '-lsl' in pilot.xws:
                group = "Left-Side Legal"
            elif pilot.shipAbility:
                group = pilot.shipAbility["name"]
                if group not in pilots.keys():
                    # Hack to insert ability at the front of the dict
                    pilots = {**{group: []}, **pilots}
            else:
                group = 'Standard'
            pilots[group].append(pilot)
        # Filter and sort the results
        out_pilots = {}
        for group, plist in pilots.items():
            if len(plist) > 0:
                out_pilots[group] = sorted(plist, key=lambda p: ((p.initiative * 100) + p.cost), reverse=True)
        return out_pilots

class Damage(Card):
    def __init__(self, card_data, db, deck):
        if card_data.get('sides', None):
            raise NotImplementedError('Damage cards should only have one side.')
        super().__init__(card_data, db)
        self.name = self.title
        self.deck = deck
        return

    def __str__(self):
        out = f'{{atkcrit}} {self.bold(self.title)} ({self.deck}) {"•" * self.amount}\n'
        out += f'{self.token_text}\n'
        out = out.replace('Action:', f'\n{self.bold("Action:")}')
        out = out.format_map(self.emoji_map)
        return out

    @property
    def unique_name(self):
        ret = self.title.lower().replace(' ', '_') + '-'
        ret += 'damage'
        return ret

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

    @property
    def unique_name(self):
        ret = self.xws + '%'  # XWS for condition is just slugged title
        ret += 'condition'
        return ret

class ShipDb(object):
    def __init__(self, pilots_json, db):
        self.db = db
        self.factions = {}
        for jfaction in pilots_json:
            fname = jfaction['faction']
            jships = self.db.get_json(jfaction['ships'])
            self.factions[fname] = {ship['xws']: Ship(ship, fname, db) for ship in jships}

    def __getitem__(self, name):
        # Search the DB by xws.
        # Return a list of matching ships for clashing xws (e.g. fangfighter, tielnfighter)
        ret = []
        for ships in self.factions.values():
            if name in ships:
                ret.append(ships[name])
        if len(ret) == 1:
            return ret[0]
        elif len(ret) > 1:
            return ret
        else:
            raise KeyError(name)

class SearchString(object):
    def __init__(self, search_string):
        self.search_text = search_string

def test_search(db: XwingDB):
    q = input('Enter query, X to exit:')
    while q != 'X':
        found = db.search_cards(q, test=True)
        for i in found:
            print(f'{i[1]:5}: {i[0].name}')
        q = input('Enter query, X to exit:')

def main():
    logger.setLevel(logging.DEBUG)
    db = XwingDB()
    test_search(db)
    pass


if __name__ == '__main__':
    main()

