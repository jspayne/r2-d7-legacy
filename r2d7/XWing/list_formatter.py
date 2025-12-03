import logging
import json
from r2d7.XWing.legality import ListLegality, Legality
from r2d7.DiscordR3.discord_formatter import discord_formatter as fmt

logger = logging.getLogger(__name__)

class ListFormatter(object):
    def __init__(self, db, xws):
        super().__init__()
        self.db = db
        if isinstance(xws, str):
            self.xws = json.loads(xws)
        elif isinstance(xws, dict):
            self.xws = xws
        else:
            logger.error(f'Invalid XWS format:\n{xws}')

    def get_upgrade_data(self, pilot):
        cards = []
        if 'upgrades' in pilot:
            for slot, upgrades in pilot['upgrades'].items():
                for upgrade in upgrades:
                    try:
                        cards.append(self.db.upgrades_xws_index[upgrade])
                    except KeyError:
                        cards.append(None)
        return cards

    def print_list(self, url=None):
        name = self.xws.get('name', 'Nameless Squadron')
        if 'vendor' in self.xws:
            if len(list(self.xws['vendor'].keys())) > 1:
                logger.warning(f"More than one vendor found! {self.xws['vendor']}")
            if vendor := list(self.xws['vendor'].values()):
                vendor = vendor[0]
                if 'link' in vendor:
                    url = vendor['link']
        if url:
            name = fmt.link(url, name)
        title = f"{{{self.xws['faction']}}} {fmt.bold(name)} "  # extra space needed because points are added below
        output = [title.format_map(fmt.emoji_map)]
        squad_points = 0
        legality = ListLegality(Legality.standard)

        for pilot in self.xws['pilots']:
            try:
                pilot_card = self.db.pilots_xws_index[pilot['id']]
            except KeyError:
                # Unrecognised pilot
                output.append('{question}' * 2 + ' ' +
                              fmt.italics(f'Unknown Pilot: {pilot["id"]}'))
                continue
            pilot_points = pilot_card.get_cost()
            legality.update(pilot_card)
            upgrade_data = self.get_upgrade_data(pilot)
            upgrades = []
            for upgrade in upgrade_data:
                if upgrade is None:
                    upgrades.append(fmt.bold('Unrecognised Upgrade'))
                    continue
                if upgrade.sides is not None:
                    side = upgrade.sides[0]
                else:
                    side = upgrade
                upgrade_text = f'{side.wiki_link(upgrade.name)}({upgrade.get_cost(pilot_card)})'
                upgrades.append(upgrade_text)
                legality.update(upgrade)
                pilot_points += upgrade.get_cost(pilot=pilot_card)

            ship_line = pilot_card.pilot_line()
            if upgrades:
                ship_line += f": {', '.join(upgrades)}"
            ship_line += f' {fmt.bold(f"[{pilot_points}]")}'

            output.append(ship_line)
            squad_points += pilot_points

        output[0] += fmt.bold(f"[{squad_points}]")
        if legality.value != Legality.banned:
            output[0] += f' {fmt.bold(f"[{str(legality)}]")}'
        return output
