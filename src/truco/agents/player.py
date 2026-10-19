"""Players of the match (Specification 4 and 5; How the Agents Decide 3 and 4).

Player is the agent: who it is, where it sits, and what it believes. How it plays
is a behaviour plugged into it:

    Player("p1@localhost", ..., behaviour=Grinder())

TrucoBehaviour is the generic behaviour: it reacts to every event from the table,
keeps the player's beliefs up to date and runs the decision recipe shared by
everyone. The rules that change from one personality to another are abstract
methods, implemented by the four personalities at the end of this file.
"""

from abc import abstractmethod
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from statistics import mean

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour

from truco import config
from truco.communication import create_message, game_template, read_message
from truco.config import (
    ADVANTAGE_WEIGHT_IN_THRESHOLDS,
    BREAK_EVEN,
    CALL_ANNOUNCES,
    CARD_COEFFICIENT,
    CARDS_PER_HAND,
    CATEGORY_VALUE,
    FOLD_BONUS_INITIAL_CALLS,
    FOLD_BONUS_INITIAL_FOLDS,
    FOLD_BONUS_WEIGHT,
    GRINDER_THREAT_TRUST,
    LOOSE_CANNON_BIAS_PER_ADVANTAGE,
    MAX_GUESS,
    MIN_GUESS,
    NOT_LISTENING_FACTOR,
    OWN_HAND_WEIGHT,
    POINTS_TO_WIN,
    ROUND_BALANCE_WEIGHT,
    TEAM,
    TURN_TIMEOUT,
    Category,
    Event,
    Performative,
    Personality,
    Rank,
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


# ============================================================================
# Generic behaviour
# ============================================================================


class TrucoBehaviour(CyclicBehaviour):
    """Reconsideration on events (Specification 4.3): the player only acts when a message arrives.

    Every message goes to the handler of its event. Notices only update the
    beliefs; requests (YOUR_TURN, ASK_DECLARATION, ASK_RESPONSE, TALK_WINDOW) also
    make the player decide and answer.
    """

    agent: "Player"
    personality: Personality  # each personality defines it

    async def run(self) -> None:
        # In SPADE, receive() without a timeout returns at once; with one, it waits for a message
        msg = await self.receive(timeout=TURN_TIMEOUT)
        if msg is None:
            return
        event, data = read_message(msg)
        handler = self.handlers.get(event)
        if handler is not None:
            await handler(data)

    @property
    def handlers(self) -> dict[Event, Callable[[dict], Awaitable[None]]]:
        return {
            Event.NEW_POINT: self.on_new_point,
            Event.CARD_PLAYED: self.on_card_played,
            Event.CALL: self.on_call,
            Event.DECLARATION: self.on_declaration,
            Event.RESPONSE: self.on_response,
            Event.ROUND_END: self.on_round_end,
            Event.POINT_END: self.on_point_end,
            Event.MATCH_END: self.on_match_end,
            Event.YOUR_TURN: self.on_your_turn,
            Event.ASK_DECLARATION: self.on_ask_declaration,
            Event.ASK_RESPONSE: self.on_ask_response,
            Event.TALK_WINDOW: self.on_talk_window,
            Event.READING: self.on_reading,
        }

    async def tell(self, recipient: str, performative: Performative, content: dict) -> None:
        await self.send(create_message(recipient, performative, content))

    # --- Notices: they only update the beliefs (Specification 4.1) ---

    async def on_new_point(self, data: dict) -> None:
        self.agent.new_point(Hand([Card(Rank(rank)) for rank in data["cards"]]))
        self.agent.record_score(data["score"])

    async def on_card_played(self, data: dict) -> None:
        """A card on the table is a fact. If it is mine, this is the table confirming it,
        and only now it leaves my hand."""
        player, card = data["player"], Card(Rank(data["card"]))
        self.agent.played[player].append(card)
        if player == self.agent.me:
            self.agent.hand.remove(card)

    async def on_call(self, data: dict) -> None:
        """Calling truco counts as announcing a medium hand (Specification 6.4)."""
        self.agent.announcements[data["player"]] = Announcement(CALL_ANNOUNCES, Source.CALL)

    async def on_declaration(self, data: dict) -> None:
        self.agent.announcements[data["player"]] = Announcement(
            Category(data["category"]), Source.DECLARATION
        )

    async def on_response(self, data: dict) -> None:
        """Feeds the fold history (folds / calls received). Raising is not folding."""
        player = data["player"]
        self.agent.calls_received[player] += 1
        if Response(data["response"]) == Response.FOLD:
            self.agent.folds[player] += 1

    async def on_round_end(self, data: dict) -> None:
        winner = data["winner"]
        self.agent.rounds.append(None if winner is None else winner == self.agent.team)

    async def on_point_end(self, data: dict) -> None:
        self.agent.record_score(data["score"])

    async def on_match_end(self, data: dict) -> None:
        await self.agent.stop()

    async def on_reading(self, data: dict) -> None:
        """Answer from the board to a LISTEN or SPY (docs/arquitetura_blackboard_truco.pdf)."""
        # TODO: turn what was read into announcements (Source.PARTNER_SIGNAL or Source.SPIED_SIGNAL).
        # - A partner signal heard without having chosen LISTEN gets attentive=False (×0.7, 3.7).
        # - Open with the board team: it sends {player: value}, but the documents talk about
        #   categories (weak/medium/strong). Agree on what travels.
        raise NotImplementedError

    # --- Requests: decide and answer (Specification 4.4) ---

    async def on_your_turn(self, data: dict) -> None:
        """Either call truco or play a card. If the call is accepted, the table sends
        YOUR_TURN again (Specification 2.4, rule 8) and this runs once more."""
        table = self.agent.table
        if data["can_call"] and self.should_call():
            await self.tell(table, Performative.PROPOSE, {"event": Event.CALL})
            return
        card = self.choose_card()
        await self.tell(table, Performative.INFORM, {"event": Event.CARD_PLAYED, "card": card.rank})

    async def on_ask_declaration(self, data: dict) -> None:
        await self.tell(
            self.agent.table,
            Performative.INFORM,
            {"event": Event.DECLARATION, "category": self.declare()},
        )

    async def on_ask_response(self, data: dict) -> None:
        response = self.answer_call(data["value"])
        performative = {
            Response.FOLD: Performative.REJECT,
            Response.ACCEPT: Performative.ACCEPT,
            Response.RAISE: Performative.PROPOSE,
        }[response]
        await self.tell(self.agent.table, performative, {"event": Event.RESPONSE, "response": response})

    async def on_talk_window(self, data: dict) -> None:
        """One talk action per round, declared to the board (Specification 6.2)."""
        # TODO:
        # 1. action = self.talk()
        # 2. value: SEND -> my true category; BLUFF -> Category.STRONG; others -> None.
        # 3. await self.tell(self.agent.board, Performative.REQUEST,
        #        {"event": Event.DECLARE, "round": ..., "action": action, "value": value})
        #    The table does not send the round number in TALK_WINDOW yet.
        # 4. LISTEN and SPY get the answer later, in on_reading. A REJECT from the board
        #    must be treated as NOTHING.
        raise NotImplementedError

    # --- Shared recipe (How the Agents Decide 3.2–3.5, summary in Appendix A) ---

    def unseen_cards(self) -> list[Card]:
        """The deck minus my cards and every card already played (3.3)."""
        seen = Counter(self.agent.hand)
        for cards in self.agent.played.values():
            seen.update(cards)
        return list((FULL_DECK - seen).elements())

    def advantage(self) -> float:
        """(our points − their points) / 12, from −1 to +1 (3.4)."""
        return (self.agent.score_ours - self.agent.score_theirs) / POINTS_TO_WIN

    def round_balance(self) -> int:
        """Rounds my team won in this point minus rounds it lost. Ties count 0 (3.4)."""
        return self.agent.rounds.count(True) - self.agent.rounds.count(False)

    def hand_strength(self) -> float:
        """With no cards left, my last card played is the one still disputing this round (3.2)."""
        if len(self.agent.hand) > 0:
            return self.agent.hand.strength
        return self.agent.played[self.agent.me][-1].power

    def belief_about(self, player: str) -> float:
        """Neutral guess -> + bias -> mixed with announcements according to trust (3.3)."""
        # 1. Neutral guess: mean power of the cards I have not seen
        neutral = mean(card.power for card in self.unseen_cards())

        # 2. Personal guess: shifted by the personality's bias
        guess = clip(neutral + self.bias(player), MIN_GUESS, MAX_GUESS)

        # 3. Announcement heard: mixed with the guess in proportion to trust
        value = guess
        announcement = self.agent.announcements.get(player)
        if announcement is not None:
            confidence = self.trust(player, announcement.category, announcement.source)
            if not announcement.attentive:
                confidence *= NOT_LISTENING_FACTOR
            value = confidence * CATEGORY_VALUE[announcement.category] + (1 - confidence) * guess

        # 4. Mean of the 3 cards: the played ones with their real power, the rest with the value
        played = self.agent.played[player]
        remaining = CARDS_PER_HAND - len(played)
        return (sum(card.power for card in played) + remaining * value) / CARDS_PER_HAND

    def threat(self) -> float:
        """Mean of the beliefs about the two opponents (3.4)."""
        return mean(self.belief_about(opponent) for opponent in self.agent.opponents)

    def win_chance(self) -> float:
        """Chance of winning the point, without the Maverick's fold bonus (3.4)."""
        p = self.personality.score_weight
        team_strength = (
            OWN_HAND_WEIGHT * self.hand_strength()
            + (1 - OWN_HAND_WEIGHT) * self.belief_about(self.agent.partner)
        )
        chance = (
            0.5
            + CARD_COEFFICIENT * (1 - p) * (team_strength - self.threat())
            + p * self.advantage()
            + ROUND_BALANCE_WEIGHT * self.round_balance()
        )
        return clip(chance, 0.0, 1.0)

    def fold_threshold(self, value_called: int) -> float:
        """Below this chance, folding is worth more than accepting (3.5)."""
        return (
            BREAK_EVEN[value_called]
            + self.personality.caution
            + ADVANTAGE_WEIGHT_IN_THRESHOLDS * self.advantage()
        )

    def raise_threshold(self) -> float:
        """Above this chance, call truco or raise (3.5)."""
        return self.personality.raise_base + ADVANTAGE_WEIGHT_IN_THRESHOLDS * self.advantage()

    # --- Decisions (Specification 4.4). Same rule for every personality. ---

    def should_call(self) -> bool:
        """On my turn, from the 2nd round: call truco (or raise)? (3.5)"""
        # TODO: win_chance() + call_bonus() > raise_threshold()
        raise NotImplementedError

    def answer_call(self, value_called: int) -> Response:
        """Someone called: fold, accept or raise (3.5)."""
        # TODO:
        # - fold   if win_chance() < fold_threshold(value_called)  (WITHOUT call_bonus: the
        #          opponent's fold history does not change the risk of accepting)
        # - raise  if the rules allow it and win_chance() + call_bonus() > raise_threshold()
        #          (the table only knows "can raise" inside Bet.can_call; it does not send it yet)
        # - accept otherwise
        raise NotImplementedError

    def choose_card(self) -> Card:
        """Which card to play (Specification 4.5; How the Agents Decide 3.6)."""
        # TODO:
        # 1. Last card: no decision, play it.
        # 2. Answering (someone already played this round), same rule for everyone:
        #    - the highest card on the table is my partner's (and no opponent card ties it):
        #      play the weakest;
        #    - otherwise the weakest that still beats it (Hand.weakest_that_beats);
        #    - if none beats it, the weakest.
        #    The cards of the current round are the last ones in self.agent.played of each player.
        # 3. Opening the round: self.open_round() (the personality decides).
        raise NotImplementedError

    def declare(self) -> Category | None:
        """Public declaration before answering a call: always the true category (6.3)."""
        # TODO: category of hand_strength() (truco.game.category_of covers the empty hand)
        raise NotImplementedError

    def talk(self) -> TalkAction:
        """Draw from the personality's talk table after the common-sense rules (3.7)."""
        # TODO:
        # - with a strong hand, the weight of BLUFF moves to SEND;
        # - whoever already sent this point, or has no cards, cannot SEND;
        # - whoever has no cards cannot BLUFF;
        # - draw among what is left in proportion to self.personality.talk.
        raise NotImplementedError

    # --- What changes with the personality ---
    # CyclicBehaviour already uses ABCMeta, so @abstractmethod is enforced here.

    @abstractmethod
    def bias(self, player: str) -> float:
        """How much I shift my guess about `player` (3.3)."""

    @abstractmethod
    def trust(self, speaker: str, category: Category, source: Source) -> float:
        """How much I believe an announcement about `speaker` (3.3).

        The ×0.7 for whoever did not choose "listen" is applied by belief_about, on top
        of this value."""

    @abstractmethod
    def call_bonus(self) -> float:
        """Added to the chance only for calling/raising, never for folding (3.4)."""

    @abstractmethod
    def open_round(self) -> Card:
        """Which card to open the round with (3.6)."""


# ============================================================================
# Personalities (How the Agents Decide 4)
# ============================================================================


class RationalShark(TrucoBehaviour):
    personality = config.RATIONAL_SHARK

    def bias(self, player: str) -> float:
        if player == self.agent.partner:
            return self.personality.partner_bias
        return self.personality.opponent_bias

    def trust(self, speaker: str, category: Category, source: Source) -> float:
        return self.personality.trust

    def call_bonus(self) -> float:
        return 0.0

    def open_round(self) -> Card:
        """Fixed rule: the strongest if its power beats the threat, otherwise the weakest."""
        hand = self.agent.hand
        strongest = hand.strongest()
        if strongest.power > self.threat():
            return strongest
        return hand.weakest()


class MaverickBluffer(TrucoBehaviour):
    personality = config.MAVERICK_BLUFFER

    # Against control players the rate is fixed at the neutral value (3.4): a Coward
    # folds every time and would give a bonus that is not skill.
    opponents_are_control: bool = False

    def bias(self, player: str) -> float:
        if player == self.agent.partner:
            return self.personality.partner_bias
        return self.personality.opponent_bias

    def trust(self, speaker: str, category: Category, source: Source) -> float:
        return self.personality.trust

    def call_bonus(self) -> float:
        """FOLD_BONUS_* applied to the history of whoever would answer my call."""
        target = self.agent.opponents[0]  # plays right after me: answers my call
        folds = 0 if self.opponents_are_control else self.agent.folds[target]
        calls = 0 if self.opponents_are_control else self.agent.calls_received[target]
        fold_rate = (folds + FOLD_BONUS_INITIAL_FOLDS) / (calls + FOLD_BONUS_INITIAL_CALLS)
        return FOLD_BONUS_WEIGHT * fold_rate

    def open_round(self) -> Card:
        # TODO: draw with personality.opening_3 (3 cards) or opening_2 (2 cards)
        raise NotImplementedError


class LooseCannon(TrucoBehaviour):
    personality = config.LOOSE_CANNON

    def bias(self, player: str) -> float:
        """About opponents: LOOSE_CANNON_BIAS_PER_ADVANTAGE × advantage."""
        if player == self.agent.partner:
            return self.personality.partner_bias
        return LOOSE_CANNON_BIAS_PER_ADVANTAGE * self.advantage()

    def trust(self, speaker: str, category: Category, source: Source) -> float:
        return self.personality.trust

    def call_bonus(self) -> float:
        return 0.0

    def open_round(self) -> Card:
        # TODO: draw with personality.opening_3 (3 cards) or opening_2 (2 cards)
        raise NotImplementedError


class Grinder(TrucoBehaviour):
    personality = config.GRINDER

    def bias(self, player: str) -> float:
        if player == self.agent.partner:
            return self.personality.partner_bias
        return self.personality.opponent_bias

    def trust(self, speaker: str, category: Category, source: Source) -> float:
        """Partner: the normal trust. Opponent: GRINDER_THREAT_TRUST if it is a threat
        (strong announcement or call), otherwise 0."""
        if speaker == self.agent.partner:
            return self.personality.trust
        if category == Category.STRONG or source == Source.CALL:
            return GRINDER_THREAT_TRUST
        return 0.0

    def call_bonus(self) -> float:
        return 0.0

    def open_round(self) -> Card:
        # TODO: draw with personality.opening_3 (3 cards) or opening_2 (2 cards)
        raise NotImplementedError


# ============================================================================
# The agent
# ============================================================================


class Player(Agent):
    """Who the player is and what it believes (Specification 4.1). How it plays is the
    behaviour it receives."""

    def __init__(
        self,
        jid: str,
        password: str,
        team: TEAM,
        table: str,
        board: str,
        partner: str,
        opponents: list[str],
        behaviour: TrucoBehaviour,
    ) -> None:
        """`opponents[0]` must be the one who plays right after me: he answers my calls."""
        super().__init__(jid, password)
        self.team = team
        self.table = table
        self.board = board
        self.me = str(self.jid.bare)
        self.partner = partner
        self.opponents = list(opponents)
        self.behaviour = behaviour

        # Beliefs. Facts and raw announcements only: interpreting them (bias, trust) is
        # the behaviour's job, because it depends on the personality.
        self.hand = Hand()
        self.played: dict[str, list[Card]] = {}  # cards each player put on the table this point
        self.announcements: dict[str, Announcement] = {}  # the latest one about each player
        self.rounds: list[bool | None] = []  # this point, from my side: won, lost, None = tie
        self.score_ours = 0
        self.score_theirs = 0
        # Fold history: the only memory that survives from one point to the next
        self.folds: Counter[str] = Counter()
        self.calls_received: Counter[str] = Counter()

    async def setup(self) -> None:
        self.add_behaviour(self.behaviour, game_template())

    @property
    def everyone(self) -> list[str]:
        return [self.me, self.partner, *self.opponents]

    def new_point(self, hand: Hand) -> None:
        """Resets everything that belongs to the point. Score and fold history survive."""
        self.hand = hand
        self.played = {player: [] for player in self.everyone}
        self.announcements = {}
        self.rounds = []

    def record_score(self, score: dict[TEAM, int]) -> None:
        self.score_ours = score[self.team]
        self.score_theirs = sum(points for team, points in score.items() if team != self.team)
