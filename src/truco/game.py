"""Game rules, without SPADE (Specification, Section 2). The numbers come from truco.config."""

import random
from collections.abc import Iterator
from dataclasses import dataclass, field
from statistics import mean

from truco.config import (
    BET_LEVELS,
    CARDS,
    CARDS_PER_HAND,
    MANILHA_POSITION,
    MAX_POSITION,
    MIN_ROUND_TO_CALL,
    POWER_EXPONENT,
    STRONG_FROM,
    TEAM,
    TEAMS,
    WEAK_BELOW,
    Category,
    Rank,
)


def team_of(players: list[str], player: str) -> TEAM:

    """Seats alternate teams: 1st and 3rd are A, 2nd and 4th are B."""
    return TEAMS[players.index(player) % 2]

@dataclass(frozen=True)
class Card:
    rank: Rank

    @property
    def position(self) -> int:
        return CARDS[self.rank].position

    @property
    def power(self) -> float:
        return (self.position / MAX_POSITION) ** POWER_EXPONENT

    @property
    def is_manilha(self) -> bool:
        return self.position >= MANILHA_POSITION

def category_of(strength: float) -> Category:
    """Kept apart from Hand because the BDI also classifies the strength of whoever played everything."""
    if strength < WEAK_BELOW:
        return Category.WEAK
    if strength < STRONG_FROM:
        return Category.MEDIUM
    return Category.STRONG

@dataclass
class Hand:
    """The cards a player still holds."""

    cards: list[Card] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.cards)

    def __iter__(self) -> Iterator[Card]:
        return iter(self.cards)

    def __contains__(self, card: Card) -> bool:
        return card in self.cards

    def remove(self, card: Card) -> None:
        """Removes one copy of the card. Error if it is not in the hand."""
        self.cards.remove(card)

    @property
    def strength(self) -> float:
        """Mean power of the cards. Error if the hand is empty."""
        return mean(card.power for card in self.cards)

    @property
    def category(self) -> Category:
        return category_of(self.strength)

    @property
    def has_manilha(self) -> bool:
        return any(card.is_manilha for card in self.cards)

    def strongest(self) -> Card:
        return max(self.cards, key=lambda card: card.position)

    def weakest(self) -> Card:
        return min(self.cards, key=lambda card: card.position)

    def weakest_that_beats(self, target: Card) -> Card | None:
        """The weakest card that beats `target`, or None if none does."""
        winners = [card for card in self.cards if card.position > target.position]
        return min(winners, key=lambda card: card.position, default=None)

@dataclass
class Deck:
    cards: list[Card] = field(init=False)
    rng: random.Random  = field(default_factory=random.Random)

    def __post_init__(self):
        self.cards = self.build_deck()

    def build_deck(self) -> list[Card]:
        """Creates the right number of copies of each card"""
        deck = []
        for rank, info in CARDS.items():
            deck.extend([Card(rank)] * info.copies)

        return deck

    def shuffle(self) -> None:
        """Shuffles the deck"""
        self.rng.shuffle(self.cards)

    def deal(self, players: list[str]) -> dict[str, Hand]:
        """
        Receives the list of player agents' JIDs
        Returns a dictionary player -> hand
        """
        hands = {}
        for player in players:
            hands[player] = Hand([self.cards.pop() for _ in range(CARDS_PER_HAND)])
        return hands

# One round on the table: (player, card) in the order they were played
CardsOnTable = list[tuple[str, Card]]

@dataclass
class Point:
    """
    A point: best of 3 rounds

    The player list comes in A-B-A-B order. The table creates a new Point for each point.
    """
    players: list[str]
    results: list[TEAM | None] = field(default_factory=list)  # None = tie

    def round_winner(self, cards_on_table: CardsOnTable) -> TEAM | None:
        """Team of the highest card. If the highest cards belong to different teams, tie (None)."""

        highest = max(card.position for _, card in cards_on_table)
        teams: set[TEAM] = {
            team_of(self.players, player)
            for player, card in cards_on_table
            if card.position == highest
        }

        if len(teams) == 1:
            return next(iter(teams))
        return None

    def record_round(self, cards_on_table: CardsOnTable) -> TEAM | None:
        """Decides the round and stores the result."""
        winner = self.round_winner(cards_on_table)
        self.results.append(winner)
        return winner

    def who_starts(self, cards_on_table: CardsOnTable) -> str:
        """
        The winner starts. If the partners tied
        on the winning card, whoever played first starts.
        If the round was a tie, whoever opened it opens again
        """

        winner = self.round_winner(cards_on_table)
        if winner is None:
            return cards_on_table[0][0] # returns the first player

        highest = max(card.position for _, card in cards_on_table)
        for player, card in cards_on_table:
            if card.position == highest and team_of(self.players, player) == winner:
                return player

        raise AssertionError("unreachable")

    def _decision(self) -> tuple[bool, TEAM | None]:
        """
        Defines the winner of the point, or None if nobody won
        """

        results = self.results

        for team in TEAMS:
            if results.count(team) >= 2:
                return True, team

        if not results:
            return False, None

        if results[0] is None:
            # 1st was a tie: whoever wins a round afterwards wins
            for result in results[1:]:
                if result is not None:
                    return True, result

            # 3 ties return None, nobody won
            return len(results) == 3, None

        # 1st had a winner: a tie in the 2nd or 3rd gives the point to them
        if None in results[1:]:
            return True, results[0]

        # 1st and 2nd with different winners, the game goes on
        return False, None

    @property
    def current_round(self) -> int:
        """Number of the round being played now: 1, 2 or 3."""
        return len(self.results) + 1

    @property
    def finished(self) -> bool:
        return self._decision()[0]

    def point_winner(self) -> TEAM | None:
        """Only meaningful once the point is finished. None = nobody scores."""
        return self._decision()[1]

@dataclass
class Bet:
    """
    Flow: call() opens a pending call; whoever answers calls accept(), fold()
    or raise_bet(). Raising means accepting the current level and calling the next one.
    """

    players: list[str]
    value: int = 1                      # how much the point is worth now
    pending: int | None = None          # value called, waiting for an answer
    caller: str | None = None
    last_team: TEAM | None = None       # who made the last raise (rule 7)

    def _next_level(self) -> int | None:
        current = self.pending if self.pending is not None else self.value
        i = BET_LEVELS.index(current)
        return BET_LEVELS[i + 1] if i + 1 < len(BET_LEVELS) else None

    def can_call(self, player: str, round_number: int) -> bool:
        """
        Valid both for calling on one's turn and for raising when answering.
        The table still checks whether it is their turn (rule 2) or whether they are the one answering.
        """
        return (
            round_number >= MIN_ROUND_TO_CALL
            and self._next_level() is not None
            and team_of(self.players, player) != self.last_team
        )

    def responder(self, caller: str) -> str:
        """The next one in play order, who is always from the other team."""
        i = self.players.index(caller)
        return self.players[(i + 1) % len(self.players)]

    def call(self, player: str) -> int:
        """Opens the call and returns the value called. Validate first with can_call."""
        level = self._next_level()
        assert level is not None
        self.pending = level
        self.caller = player
        self.last_team = team_of(self.players, player)
        return level

    def accept(self) -> None:
        assert self.pending is not None
        self.value = self.pending
        self.pending = None

    def fold(self) -> tuple[TEAM, int]:
        """Ends the point: the caller takes the value from before the call."""
        assert self.pending is not None and self.caller is not None
        self.pending = None
        return team_of(self.players, self.caller), self.value

    def raise_bet(self, player: str) -> int:
        """Accepts the current call and calls the next level."""
        self.accept()
        return self.call(player)
