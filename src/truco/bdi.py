"""Reasoning of the deliberative players (Specification 4; How the Agents Decide 3).

One recipe, many knobs: BDIPlayer implements the recipe only once, and each
personality is a subclass that only swaps the Personality (the knobs) and, when
needed, overrides one of the three hooks for the special rules. All numbers
(knobs and recipe constants) live in truco.config.
"""

from collections import Counter

from truco.agents.player import Player
from truco.config import Category, Event, Personality, Response, TalkAction
from truco.game import Card, Deck, Hand

# The 29 cards, counted by rank (there are 4 queens, 2 jokers...)
FULL_DECK: Counter[Card] = Counter(Deck().cards)


class Beliefs:
    """Only facts and raw announcements. Interpreting them (bias, trust) is the agent's
    job, because it depends on the personality."""

    def __init__(self, me: str, partner: str, opponents: list[str]) -> None:
        self.me = me
        self.partner = partner
        self.opponents = list(opponents)
        self.hand = Hand()
        self.played: dict[str, list[Card]] = {}  # cards each player put on the table this point

    @property
    def everyone(self) -> list[str]:
        return [self.me, self.partner, *self.opponents]

    def new_point(self, hand: Hand) -> None:
        """Resets everything that belongs to the point. The fold history survives.

        `hand` is kept by reference: it is the same object as the agent's hand, and
        record_card is the one that removes my cards from it when the table confirms.
        """
        self.hand = hand
        self.played = {player: [] for player in self.everyone}

    def record_card(self, player: str, card: Card) -> None:
        """A card on the table is a fact (Specification 4.1). If it is mine, it leaves my hand."""
        self.played[player].append(card)
        if player == self.me:
            self.hand.remove(card)

    def record_announcement(self, about: str, category: Category, source: str) -> None:
        """The most recent one per player is the one that counts (3.3)."""
        raise NotImplementedError

    def record_response(self, player: str, response: Response) -> None:
        """Feeds the fold history (folds / calls received)."""
        raise NotImplementedError

    def unseen_cards(self) -> list[Card]:
        """The deck minus my cards and every card already played (How the Agents Decide 3.3)."""
        seen = Counter(self.hand)
        for cards in self.played.values():
            seen.update(cards)
        return list((FULL_DECK - seen).elements())

    def advantage(self) -> float:
        raise NotImplementedError

    def round_balance(self) -> int:
        raise NotImplementedError


class BDIPlayer(Player):
    personality: Personality  # each subclass defines it

    async def setup(self) -> None:
        self.beliefs = Beliefs(str(self.jid.bare), self.partner, self.opponents)
        await super().setup()

    def perceive(self, event: Event, data) -> None:
        """Turns each event into a Beliefs update.
        Remember: a CALL also counts as a "medium" announcement by the caller (Specification 6.4)."""
        raise NotImplementedError

    # --- Shared recipe (How the Agents Decide 3.2–3.5, summary in Appendix A) ---

    def hand_strength(self) -> float:
        """self.hand.strength; with an empty hand, the power of the card played this round."""
        raise NotImplementedError

    def belief_about(self, player: str) -> float:
        """Neutral guess -> + bias -> mixed with announcements according to trust."""
        raise NotImplementedError

    def win_chance(self) -> float:
        raise NotImplementedError

    def fold_threshold(self, value_called: int) -> float:
        raise NotImplementedError

    def raise_threshold(self) -> float:
        raise NotImplementedError

    # --- Decisions (implement the Player contract) ---

    def should_call(self) -> bool:
        raise NotImplementedError

    def answer_call(self, value_called: int) -> Response:
        raise NotImplementedError

    def choose_card(self) -> Card:
        """Last card / answering (same rule for everyone) / opening (hook)."""
        raise NotImplementedError

    def declare(self) -> Category:
        raise NotImplementedError

    def talk(self) -> TalkAction:
        """Draw from the personality's table + common-sense rules (3.7)."""
        raise NotImplementedError

    # --- Hooks: the default reads the knobs; special personalities override ---

    def bias(self, player: str) -> float:
        raise NotImplementedError

    def trust(self, speaker: str, category: Category, source: str) -> float:
        """Includes the ×0.7 for whoever did not choose "listen"."""
        raise NotImplementedError

    def call_bonus(self) -> float:
        """Added to the chance only for calling/raising. Default: 0."""
        return 0.0

    def open_round(self) -> Card:
        """Default: draw with opening_3 / opening_2."""
        raise NotImplementedError
