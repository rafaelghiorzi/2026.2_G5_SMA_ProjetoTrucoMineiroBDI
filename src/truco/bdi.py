"""Reasoning of the deliberative players (Specification 4; How the Agents Decide 3).

One recipe, many knobs: BDIPlayer implements the recipe only once, and each
personality is a subclass that only swaps the Personality (the knobs) and, when
needed, overrides one of the three hooks for the special rules. All numbers
(knobs and recipe constants) live in truco.config.
"""

from collections import Counter
from dataclasses import dataclass
from statistics import mean

from truco.agents.player import Player
from truco.config import (
    ADVANTAGE_WEIGHT_IN_THRESHOLDS,
    BREAK_EVEN,
    CARD_COEFFICIENT,
    CARDS_PER_HAND,
    CATEGORY_VALUE,
    MAX_GUESS,
    MIN_GUESS,
    NOT_LISTENING_FACTOR,
    OWN_HAND_WEIGHT,
    POINTS_TO_WIN,
    ROUND_BALANCE_WEIGHT,
    Category,
    Event,
    Personality,
    Response,
    Source,
    TalkAction,
)
from truco.game import Card, Deck, Hand

# The 29 cards, counted by rank (there are 4 queens, 2 jokers...)
FULL_DECK: Counter[Card] = Counter(Deck().cards)


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class Announcement:
    """What someone said about a player's hand. Raw: trust is applied only when believing."""

    category: Category
    source: Source
    attentive: bool = True  # False = a partner signal heard without choosing "listen"


class Beliefs:
    """Only facts and raw announcements. Interpreting them (bias, trust) is the agent's
    job, because it depends on the personality."""

    def __init__(self, me: str, partner: str, opponents: list[str]) -> None:
        self.me = me
        self.partner = partner
        self.opponents = list(opponents)
        self.hand = Hand()
        self.played: dict[str, list[Card]] = {}  # cards each player put on the table this point
        self.announcements: dict[str, Announcement] = {}  # the latest one about each player
        self.rounds: list[bool | None] = []  # this point, from my side: won, lost, None = tie
        self.score_ours = 0
        self.score_theirs = 0
        # Fold history: the only memory that survives from one point to the next
        self.folds: Counter[str] = Counter()
        self.calls_received: Counter[str] = Counter()

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
        self.announcements = {}
        self.rounds = []

    def record_card(self, player: str, card: Card) -> None:
        """A card on the table is a fact (Specification 4.1). If it is mine, it leaves my hand."""
        self.played[player].append(card)
        if player == self.me:
            self.hand.remove(card)

    def record_announcement(
        self, about: str, category: Category, source: Source, attentive: bool = True
    ) -> None:
        """The most recent one per player is the one that counts (3.3)."""
        self.announcements[about] = Announcement(category, source, attentive)

    def record_response(self, player: str, response: Response) -> None:
        """Feeds the fold history (folds / calls received). Raising is not folding."""
        self.calls_received[player] += 1
        if response == Response.FOLD:
            self.folds[player] += 1

    def record_round(self, won: bool | None) -> None:
        """Result of a round from my team's side: True, False, or None for a tie."""
        self.rounds.append(won)

    def record_score(self, ours: int, theirs: int) -> None:
        self.score_ours = ours
        self.score_theirs = theirs

    def unseen_cards(self) -> list[Card]:
        """The deck minus my cards and every card already played (How the Agents Decide 3.3)."""
        seen = Counter(self.hand)
        for cards in self.played.values():
            seen.update(cards)
        return list((FULL_DECK - seen).elements())

    def advantage(self) -> float:
        """(our points − their points) / 12, from −1 to +1 (3.4)."""
        return (self.score_ours - self.score_theirs) / POINTS_TO_WIN

    def round_balance(self) -> int:
        """Rounds my team won in this point minus rounds it lost. Ties count 0 (3.4)."""
        return self.rounds.count(True) - self.rounds.count(False)


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
        """self.hand.strength; with an empty hand, the power of the card played this round.

        With no cards left, my last card played is the one still disputing this round (3.2).
        """
        if len(self.hand) > 0:
            return self.hand.strength
        return self.beliefs.played[self.beliefs.me][-1].power

    def belief_about(self, player: str) -> float:
        """Neutral guess -> + bias -> mixed with announcements according to trust (3.3)."""
        beliefs = self.beliefs

        # 1. Neutral guess: mean power of the cards I have not seen
        neutral = mean(card.power for card in beliefs.unseen_cards())

        # 2. Personal guess: shifted by the personality's bias
        guess = clip(neutral + self.bias(player), MIN_GUESS, MAX_GUESS)

        # 3. Announcement heard: mixed with the guess in proportion to trust
        value = guess
        announcement = beliefs.announcements.get(player)
        if announcement is not None:
            confidence = self.trust(player, announcement.category, announcement.source)
            if not announcement.attentive:
                confidence *= NOT_LISTENING_FACTOR
            value = confidence * CATEGORY_VALUE[announcement.category] + (1 - confidence) * guess

        # 4. Mean of the 3 cards: the played ones with their real power, the rest with the value
        played = beliefs.played[player]
        remaining = CARDS_PER_HAND - len(played)
        return (sum(card.power for card in played) + remaining * value) / CARDS_PER_HAND

    def win_chance(self) -> float:
        """Chance of winning the point, without the Maverick's fold bonus (3.4)."""
        beliefs = self.beliefs
        p = self.personality.score_weight

        team_strength = (
            OWN_HAND_WEIGHT * self.hand_strength()
            + (1 - OWN_HAND_WEIGHT) * self.belief_about(beliefs.partner)
        )
        threat = mean(self.belief_about(opponent) for opponent in beliefs.opponents)

        chance = (
            0.5
            + CARD_COEFFICIENT * (1 - p) * (team_strength - threat)
            + p * beliefs.advantage()
            + ROUND_BALANCE_WEIGHT * beliefs.round_balance()
        )
        return clip(chance, 0.0, 1.0)

    def fold_threshold(self, value_called: int) -> float:
        """Below this chance, folding is worth more than accepting (3.5)."""
        return (
            BREAK_EVEN[value_called]
            + self.personality.caution
            + ADVANTAGE_WEIGHT_IN_THRESHOLDS * self.beliefs.advantage()
        )

    def raise_threshold(self) -> float:
        """Above this chance, call truco or raise (3.5)."""
        return self.personality.raise_base + ADVANTAGE_WEIGHT_IN_THRESHOLDS * self.beliefs.advantage()

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
        """How much I shift my guess about `player`: one value for the partner, one for opponents."""
        if player == self.beliefs.partner:
            return self.personality.partner_bias
        return self.personality.opponent_bias

    def trust(self, speaker: str, category: Category, source: Source) -> float:
        """How much I believe an announcement about `speaker`.

        The ×0.7 for whoever did not choose "listen" is applied by belief_about, on top
        of this value, so the personalities that override this hook get it for free.
        """
        return self.personality.trust

    def call_bonus(self) -> float:
        """Added to the chance only for calling/raising. Default: 0."""
        return 0.0

    def open_round(self) -> Card:
        """Default: draw with opening_3 / opening_2."""
        raise NotImplementedError
