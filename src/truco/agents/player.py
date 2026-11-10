"""Players of the match.

Player is the agent: who it is, where it sits and what it believes. How it plays is
a behaviour plugged into it:

    Player(jid, password, team, table, board, partner, opponents, Grinder())

TrucoBehaviour reacts to every message, keeps the beliefs up to date and runs the
decision recipe shared by everyone. What changes from one personality to another is
implemented by the four classes at the end of this file. See also agents/control.py.
"""

import random
import asyncio
from abc import abstractmethod
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from statistics import mean

from slixmpp import JID
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour

from truco import config
from truco.communication import create_message, game_template, read_message, LoggedSend
from truco.config import (
    ADVANTAGE_WEIGHT_IN_THRESHOLDS,
    BET_LEVELS,
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
    THINK_TIME,
    Category,
    Event,
    Performative,
    Personality,
    Rank,
    Response,
    Source,
    TalkAction,
)
from truco.game import Card, Deck, Hand, category_of

import logging
logger = logging.getLogger("truco.player")

# The 29 cards, counted by rank
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


class TrucoBehaviour(LoggedSend, CyclicBehaviour):
    """
    The player only acts when a message arrives.

    Every message goes to the handler of its event. Notices only update the
    beliefs; requests (YOUR_TURN, ASK_DECLARATION, ASK_RESPONSE, TALK_WINDOW) also
    make the player decide and answer.
    """

    agent: "Player"
    personality: Personality  # each personality defines it

    def __init__(self, rng: random.Random | None = None,
                 think_time: tuple[float, float] | None = THINK_TIME) -> None:
        """`rng` fixes the decisions; `think_time` is the delay in seconds (None = no delay)."""
        super().__init__()
        self.rng = rng or random.Random()
        self.think_time = think_time
        self.think_rng = random.Random()  # separate: the delay must not change any decision

    async def think(self) -> None:
        """
        Pretends to think before answering a request. The other agents keep running meanwhile.
        """
        if self.think_time is not None:
            await asyncio.sleep(self.think_rng.uniform(*self.think_time))

    async def run(self) -> None:
        # In SPADE, receive() without a timeout returns at once; with one, it waits for a message
        msg = await self.receive(timeout=TURN_TIMEOUT)
        if msg is None:
            return
        event, data = read_message(msg)
        handler = self.handlers.get(event)
        if handler is None:
            return
        try:
            await handler(data)
        except Exception:
            logger.exception(f"{self.agent.me} falhou o handling: {event}")
        
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

    async def tell(self, recipient: JID, performative: Performative, content: dict) -> None:
        await self.send(create_message(recipient, performative, content))

    # --- Notices: they only update the beliefs ---

    async def on_new_point(self, data: dict) -> None:
        self.agent.point_number = data["point"]
        self.agent.new_point(Hand([Card(Rank(rank)) for rank in data["cards"]]))
        self.agent.record_score(data["score"])

    async def on_card_played(self, data: dict) -> None:
        """A card on the table is a fact. If it is mine, this is the table confirming it,
        and only now it leaves my hand."""
        player, card = JID(data["player"]), Card(Rank(data["card"]))
        self.agent.played[player].append(card)
        if player == self.agent.me:
            self.agent.hand.remove(card)

    async def on_call(self, data: dict) -> None:
        """A call or raise counts as announcing a medium hand."""
        self.agent.announcements[JID(data["player"])] = Announcement(CALL_ANNOUNCES, Source.CALL)

    async def on_declaration(self, data: dict) -> None:
        self.agent.announcements[JID(data["player"])] = Announcement(
            Category(data["category"]), Source.DECLARATION
        )

    async def on_response(self, data: dict) -> None:
        """Feeds the fold history (folds / calls received). Raising is not folding."""
        player = JID(data["player"])
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
        """Turns the signals the board delivered into announcements about whoever sent them.

        data: {"point", "signals": [{"from": jid, "value": category}], "my_action": TalkAction}
        """
        if data["point"] != self.agent.point_number:
            return # Late message from a point that is already over

        listening = TalkAction(data["my_action"]) == TalkAction.LISTEN
        for signal in data["signals"]:
            sender = JID(signal["from"])
            category = Category(signal["value"])
            if sender == self.agent.partner:
                # The partner's signal always arrives; not listening only lowers the trust
                announcement = Announcement(category, Source.PARTNER_SIGNAL, attentive=listening)
            else:
                # Only a successful SPY gets here, but it may be a bluff
                announcement = Announcement(category, Source.SPIED_SIGNAL)
            self.agent.announcements[sender] = announcement

    # --- Requests: decide and answer ---

    async def on_your_turn(self, data: dict) -> None:
        """Either call truco or play a card. If the call is accepted, the table sends
        YOUR_TURN again and this runs once more."""

        await self.think()

        table = self.agent.table
        if data["can_call"] and self.should_call():
            await self.trace("call")
            await self.tell(table, Performative.PROPOSE, {"event": Event.CALL})
            return
        card = self.choose_card()
        await self.trace("play", card=card.rank)
        await self.tell(table, Performative.INFORM, {"event": Event.CARD_PLAYED, "card": card.rank})

    async def on_ask_declaration(self, data: dict) -> None:
        await self.think()

        await self.tell(
            self.agent.table,
            Performative.INFORM,
            {"event": Event.DECLARATION, "category": self.declare()},
        )

    async def on_ask_response(self, data: dict) -> None:
        await self.think()

        response = self.answer_call(data["value"])
        performative = {
            Response.FOLD: Performative.REJECT,
            Response.ACCEPT: Performative.ACCEPT,
            Response.RAISE: Performative.PROPOSE,
        }[response]
        
        await self.trace("respond", response=response, value=data["value"])
        await self.tell(self.agent.table, performative, {"event": Event.RESPONSE, "response": response})

    async def on_talk_window(self, data: dict) -> None:
        """Chooses one talk action for the point and declares it to the board.

        A failed SPY is declared as NOTHING: the board only knows about the ones that worked.
        """

        await self.think()
        action = self.talk()
        value = None

        match (action):
            case TalkAction.SPY:
                if self.rng.random() >= self.personality.spy_success:
                    action = TalkAction.NOTHING
            case TalkAction.SEND:
                value = self.agent.hand.category
            case TalkAction.BLUFF:
                value = Category.STRONG
            case _:
                pass

        await self.tell(
            recipient=self.agent.board,
            performative=Performative.REQUEST,
            content= {
                "event": Event.DECLARE,
                "point": self.agent.point_number,
                "action": action,
                "value": value
            }
        )

        return None

    # --- Shared recipe ---

    def unseen_cards(self) -> list[Card]:
        """The deck minus my cards and every card already played."""
        seen = Counter(self.agent.hand)
        for cards in self.agent.played.values():
            seen.update(cards)
        return list((FULL_DECK - seen).elements())

    def advantage(self) -> float:
        """(our points − their points) / 12, from −1 to +1."""
        return (self.agent.score_ours - self.agent.score_theirs) / POINTS_TO_WIN

    def round_balance(self) -> int:
        """Rounds my team won in this point minus rounds it lost. Ties count 0."""
        return self.agent.rounds.count(True) - self.agent.rounds.count(False)

    def hand_strength(self) -> float:
        """With no cards left, my last card played is the one still disputing this round."""
        if len(self.agent.hand) > 0:
            return self.agent.hand.strength
        return self.agent.played[self.agent.me][-1].power

    def belief_about(self, player: JID) -> float:
        """Neutral guess -> + bias -> mixed with announcements according to trust."""
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
        """Mean of the beliefs about the two opponents."""
        return mean(self.belief_about(opponent) for opponent in self.agent.opponents)

    def win_chance(self) -> float:
        """Chance of winning the point, without the Maverick's fold bonus."""
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
        """Below this chance, folding is worth more than accepting."""
        return (
            BREAK_EVEN[value_called]
            + self.personality.caution
            + ADVANTAGE_WEIGHT_IN_THRESHOLDS * self.advantage()
        )

    def raise_threshold(self) -> float:
        """Above this chance, call truco or raise."""
        return self.personality.raise_base + ADVANTAGE_WEIGHT_IN_THRESHOLDS * self.advantage()

    # --- Decisions. Same rule for every personality. ---

    def should_call(self) -> bool:
        """Call truco if the chance of winning the point is above the threshold."""
        return self.win_chance() + self.call_bonus() > self.raise_threshold()   

    def answer_call(self, value_called: int) -> Response:
        """Someone called: fold, accept or raise"""
        chance = self.win_chance()
        if chance < self.fold_threshold(value_called):   
            return Response.FOLD
        can_raise = value_called < BET_LEVELS[-1]        
        if can_raise and chance + self.call_bonus() > self.raise_threshold():
            return Response.RAISE
        return Response.ACCEPT

    def current_round_cards(self) -> dict[JID, Card]:
        """Cards of the current round: whoever played more cards than the rounds already finished.

        `rounds` gets one item per ROUND_END (ties included), so its length is the index of
        the current round inside each list of `played`."""
        finished = len(self.agent.rounds)
        return {
            player: cards[finished]
            for player, cards in self.agent.played.items()
            if len(cards) > finished
        }

    def choose_card(self) -> Card:
        """Which card to play."""
        hand = self.agent.hand
        # last card available
        if len(hand) == 1:
            return hand.cards[0]

        # if no cards on the table, open the round with the personality's opening table 
        on_table = self.current_round_cards()
        if not on_table:
            return self.open_round()

        # if my partner is winning, play the weakest card 
        highest = max(on_table.values(), key=lambda card: card.position)
        best_opponent = max(
            (card.position for player, card in on_table.items() if player in self.agent.opponents),
            default=0,
        )
        partner_card = on_table.get(self.agent.partner)
        if partner_card is not None and partner_card.position > best_opponent:
            return hand.weakest()  # my partner is already winning (a tie is not winning)
        return hand.weakest_that_beats(highest) or hand.weakest()

    def declare(self) -> Category:
        """Public declarations are always true."""
        return category_of(self.hand_strength())

    def talk(self) -> TalkAction:
        """Draws from the personality's talk table, after adjusting it for a strong hand."""
        weights = dict(self.personality.talk)  # a copy: the personality's table is shared

        # With a strong hand, the weight of BLUFF moves to SEND (bluffing only makes sense without a hand)
        if self.agent.hand.category == Category.STRONG:
            weights[TalkAction.SEND] += weights.pop(TalkAction.BLUFF)

        actions = list(weights)
        return self.rng.choices(actions, weights=[weights[action] for action in actions])[0]

    def draw_opening(self) -> Card:
        """Draw with the personality's opening table. With 2 cards there is no "medium"."""
        cards = sorted(self.agent.hand, key=lambda card: card.position)  # weak -> strong
        if len(cards) == 3:
            w = self.personality.opening_3
            if w is None:
                raise ValueError("weights are non-existent")
            options, weights = [cards[2], cards[1], cards[0]], [w.strong, w.medium, w.weak]
        else:
            w = self.personality.opening_2
            if w is None:
                raise ValueError("weights are non-existent")
            options, weights = [cards[-1], cards[0]], [w.strong, w.weak]
        return self.rng.choices(options, weights=weights)[0]

    def snapshot(self) -> dict:
        """O raciocínio atual, para a interface. Não altera nenhum estado."""
        return {
            "win_chance": round(self.win_chance(), 3),
            "own_strength": round(self.hand_strength(), 3),
            "threat": round(self.threat(), 3),
            "raise_threshold": round(self.raise_threshold(), 3),
            "advantage": round(self.advantage(), 3),
            "beliefs_about_partner": {str(self.agent.partner): self.belief_about(self.agent.partner)},
            "beliefs_about_opponents": {str(p): round(self.belief_about(p), 3) for p in self.agent.opponents},
            "announcements": {
                str(player): {"category": a.category, "source": a.source}
                for player, a in self.agent.announcements.items()
            },
        }

    async def trace(self, decision: str, **info) -> None:
        if self.agent.spectator is None:
            return
        await self.tell(self.agent.spectator, Performative.INFORM, {
            "event": Event.THOUGHT,
            "player": self.agent.me,
            "point": self.agent.point_number,
            "decision": decision,
            **self.snapshot(),
            **info,
        })
    # --- What changes with the personality ---
    # CyclicBehaviour already uses ABCMeta, so @abstractmethod is enforced here.

    @abstractmethod
    def bias(self, player: JID) -> float:
        """How much I shift my guess about `player`."""

    @abstractmethod
    def trust(self, speaker: JID, category: Category, source: Source) -> float:
        """How much I believe an announcement about `speaker`.

        The x0.7 for whoever did not choose "listen" is applied by belief_about, on top
        of this value."""

    @abstractmethod
    def call_bonus(self) -> float:
        """Added to the chance only for calling/raising, never for folding."""

    @abstractmethod
    def open_round(self) -> Card:
        """Which card to open the round with."""


# ============================================================================
# Personalities
# ============================================================================


class RationalShark(TrucoBehaviour):
    personality = config.RATIONAL_SHARK

    def bias(self, player: JID) -> float:
        if player == self.agent.partner:
            return self.personality.partner_bias
        return self.personality.opponent_bias

    def trust(self, speaker: JID, category: Category, source: Source) -> float:
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

    # Against control players the rate is fixed at the neutral value: a Coward
    # folds every time and would give a bonus that is not skill.
    opponents_are_control: bool = False

    def bias(self, player: JID) -> float:
        if player == self.agent.partner:
            return self.personality.partner_bias
        return self.personality.opponent_bias

    def trust(self, speaker: JID, category: Category, source: Source) -> float:
        return self.personality.trust

    def call_bonus(self) -> float:
        """FOLD_BONUS_* applied to the history of whoever would answer my call."""
        target = self.agent.opponents[0]  # plays right after me: answers my call
        folds = 0 if self.opponents_are_control else self.agent.folds[target]
        calls = 0 if self.opponents_are_control else self.agent.calls_received[target]
        fold_rate = (folds + FOLD_BONUS_INITIAL_FOLDS) / (calls + FOLD_BONUS_INITIAL_CALLS)
        return FOLD_BONUS_WEIGHT * fold_rate

    def open_round(self) -> Card:
        return self.draw_opening()


class LooseCannon(TrucoBehaviour):
    personality = config.LOOSE_CANNON

    def bias(self, player: JID) -> float:
        """About opponents: LOOSE_CANNON_BIAS_PER_ADVANTAGE × advantage."""
        if player == self.agent.partner:
            return self.personality.partner_bias
        return LOOSE_CANNON_BIAS_PER_ADVANTAGE * self.advantage()

    def trust(self, speaker: JID, category: Category, source: Source) -> float:
        return self.personality.trust

    def call_bonus(self) -> float:
        return 0.0

    def open_round(self) -> Card:
        return self.draw_opening()


class Grinder(TrucoBehaviour):
    personality = config.GRINDER

    def bias(self, player: JID) -> float:
        if player == self.agent.partner:
            return self.personality.partner_bias
        return self.personality.opponent_bias

    def trust(self, speaker: JID, category: Category, source: Source) -> float:
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
        return self.draw_opening()


# ============================================================================
# The agent
# ============================================================================


class Player(Agent):
    """Who the player is and what it believes. How it plays is the
    behaviour it receives."""

    def __init__(
        self,
        jid: JID,
        password: str,
        team: TEAM,
        table: JID,
        board: JID,
        partner: JID,
        opponents: list[JID],
        behaviour: TrucoBehaviour,
        spectator: JID | None = None
    ) -> None:
        """`opponents[0]` must be the one who plays right after me: they answer my calls."""
        super().__init__(str(jid), password)
        self.team: TEAM = team
        self.table = table
        self.board = board
        self.spectator = spectator
        self.point_number = 0  # which point is being played, as told by the table
        self.me = JID(self.jid.bare)
        self.partner = partner
        self.opponents = list(opponents)
        self.behaviour = behaviour

        # Beliefs. Facts and raw announcements only: interpreting them (bias, trust) is
        # the behaviour's job, because it depends on the personality.
        self.hand = Hand()
        self.played: dict[JID, list[Card]] = {}  # cards each player put on the table this point
        self.announcements: dict[JID, Announcement] = {}  # the latest one about each player
        self.rounds: list[bool | None] = []  # this point, from my side: won, lost, None = tie
        self.score_ours = 0
        self.score_theirs = 0
        # Fold history: the only memory that survives from one point to the next
        self.folds: Counter[JID] = Counter()
        self.calls_received: Counter[JID] = Counter()

    async def setup(self) -> None:
        self.add_behaviour(self.behaviour, game_template())

    @property
    def everyone(self) -> list[JID]:
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
