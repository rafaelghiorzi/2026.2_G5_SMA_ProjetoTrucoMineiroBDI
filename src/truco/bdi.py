"""Reasoning of the deliberative players (Specification 4; How the Agents Decide 3).

One recipe, many knobs: BDIPlayer implements the recipe only once, and each
personality is a subclass that only swaps the Personality (the knobs) and, when
needed, overrides one of the three hooks for the special rules. All numbers
(knobs and recipe constants) live in truco.config.
"""

from truco.agents.player import Player
from truco.config import Category, Event, Personality, Response, TalkAction
from truco.game import Card, Hand


class Beliefs:
    """Only facts and raw announcements. Interpreting them (bias, trust) is the agent's
    job, because it depends on the personality."""

    def new_point(self, hand: Hand) -> None:
        """Resets everything that belongs to the point. The fold history survives."""
        raise NotImplementedError

    def record_card(self, player: str, card: Card) -> None:
        raise NotImplementedError

    def record_announcement(self, about: str, category: Category, source: str) -> None:
        """The most recent one per player is the one that counts (3.3)."""
        raise NotImplementedError

    def record_response(self, player: str, response: Response) -> None:
        """Feeds the fold history (folds / calls received)."""
        raise NotImplementedError

    def unseen_cards(self) -> list[Card]:
        raise NotImplementedError

    def advantage(self) -> float:
        raise NotImplementedError

    def round_balance(self) -> int:
        raise NotImplementedError


class BDIPlayer(Player):
    personality: Personality  # each subclass defines it

    async def setup(self) -> None:
        self.beliefs = Beliefs()
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
