from enum import Enum

class Legality(Enum):
    standard = 1
    wild_space = 2
    epic = 3
    banned = 4

    def __lt__(self, other):
        return self.value < other.value

    def __eq__(self, other):
        return self.value == other.value

    def __str__(self):
        if self.value == Legality.epic:
            return "Epic"
        elif self.value == Legality.banned:
            return "Banned"
        elif self.value == Legality.wild_space:
            return "Wild Space"
        elif self.value == Legality.standard:
            return "Standard"
        else:
            return "Invalid Legality"

class CardLegality(object):
    def __init__(self, card: dict):
        """
        Identify the legality of a card
        This function makes the following assumptions:
        - everything legal in standard is legal in wild space,
        - everything legal in wild space is legal in epic
        """
        self.value = Legality.banned
        if card.get('epic', False):
            self.value = Legality.epic
        if card.get('wildspace', False):
            self.value = Legality.wild_space
        if card.get('standard', False):
            self.value = Legality.standard

    def __str__(self):
        if self.value == Legality.epic:
            return "Epic"
        elif self.value == Legality.banned:
            return "Banned"
        elif self.value == Legality.wild_space:
            return "Wild Space"
        elif self.value == Legality.standard:
            return "Standard"
        else:
            return "Invalid Legality"

class ListLegality(object):
    """
    Identify the legality of a list
    This function assumes that the list has the legality of the
    worst case card.
    """
    def __init__(self, legality=Legality.standard):
        self.value = legality

    def update(self, card):
        # card is type CardData, but I can't type hint it without
        # a circular import
        if self.value < card.legality.value:
            self.value = card.legality.value

    def __str__(self):
        if self.value == Legality.epic:
            return "Epic"
        elif self.value == Legality.banned:
            return "Banned"
        elif self.value == Legality.wild_space:
            return "Wild Space"
        elif self.value == Legality.standard:
            return "Standard"
        else:
            return "Invalid Legality"
