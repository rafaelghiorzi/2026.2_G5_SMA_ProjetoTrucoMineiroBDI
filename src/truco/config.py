"""Central configuration: every piece of data the game and the agents use lives here.

This module imports nothing from the project or from SPADE, so any file can
import it without creating cycles. Sections follow the documents in docs/.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, NamedTuple


# ============================================================================
# System
# ============================================================================

# SPADE's embedded XMPP server
XMPP_DOMAIN = "localhost"
AGENT_PASSWORD = "truco"

ONTOLOGY = "truco-mineiro"
TURN_TIMEOUT = 15  # seconds waiting for a play before asking again


# ============================================================================
# Cards (Specification 2.1)
# ============================================================================

class Rank(StrEnum):
    """The 11 card ranks. The text is the code that travels in messages."""

    QUEEN = "Q"
    JACK = "J"
    KING = "K"
    ACE = "A"
    TWO = "2"
    THREE = "3"
    JOKER = "JK"
    SEVEN_OF_DIAMONDS = "7D"
    ACE_OF_SPADES = "AS"
    SEVEN_OF_HEARTS = "7H"
    ZAP = "4C"  # 4 of clubs


class CardInfo(NamedTuple):
    position: int  # who beats whom: higher position wins
    copies: int  # how many exist in the deck


CARDS: dict[Rank, CardInfo] = {
    Rank.QUEEN: CardInfo(position=1, copies=4),
    Rank.JACK: CardInfo(position=2, copies=4),
    Rank.KING: CardInfo(position=3, copies=4),
    Rank.ACE: CardInfo(position=4, copies=3),  # the fourth ace is the ace of spades
    Rank.TWO: CardInfo(position=5, copies=4),
    Rank.THREE: CardInfo(position=6, copies=4),
    Rank.JOKER: CardInfo(position=7, copies=2),
    Rank.SEVEN_OF_DIAMONDS: CardInfo(position=8, copies=1),
    Rank.ACE_OF_SPADES: CardInfo(position=9, copies=1),
    Rank.SEVEN_OF_HEARTS: CardInfo(position=10, copies=1),
    Rank.ZAP: CardInfo(position=11, copies=1),
}

MANILHA_POSITION = 8  # from position 8 up, the card is a manilha
MAX_POSITION = max(info.position for info in CARDS.values())
POWER_EXPONENT = 1.5  # power = (position / max) ** exponent (How the Agents Decide 3.1)
CARDS_PER_HAND = 3


# ============================================================================
# Teams, scoring and betting (Specification 2.4)
# ============================================================================

TEAM = Literal["A", "B"]
TEAMS: tuple[TEAM, TEAM] = ("A", "B")

POINTS_TO_WIN = 12
BET_LEVELS = [1, 3, 6, 9, 12]  # no call, truco, six, nine, twelve
MIN_ROUND_TO_CALL = 2


# ============================================================================
# Hand category (How the Agents Decide 3.2 and 3.3)
# ============================================================================

class Category(StrEnum):
    """Hand category, used in signals and declarations."""

    WEAK = "weak"
    MEDIUM = "medium"
    STRONG = "strong"


WEAK_BELOW = 0.35  # strength below this: weak
STRONG_FROM = 0.60  # strength from this up: strong

# Strength each announced category stands for, to whoever hears it
CATEGORY_VALUE: dict[Category, float] = {
    Category.WEAK: 0.2,
    Category.MEDIUM: 0.5,
    Category.STRONG: 0.8,
}


# ============================================================================
# FIPA-ACL protocol (Specification 6)
# ============================================================================

class Performative(StrEnum):
    INFORM = "inform"
    REQUEST = "request"
    PROPOSE = "propose"
    ACCEPT = "accept-proposal"
    REJECT = "reject-proposal"


class Event(StrEnum):
    """What flows between table and players. The ones that ask for an answer are marked."""

    NEW_POINT = "new-point"
    YOUR_TURN = "your-turn"  # asks: a card, or a call when can_call is true
    CARD_PLAYED = "card-played"
    CALL = "call"  # player asks for truco/raise; then the table's public notice of it
    ASK_DECLARATION = "ask-declaration"  # asks: hand category (or null to skip)
    DECLARATION = "declaration"
    ASK_RESPONSE = "ask-response"  # asks the responder: fold, accept or raise
    RESPONSE = "response"  # someone folded, accepted or raised
    TALK_WINDOW = "talk-window"  # asks: talk action
    ROUND_END = "round-end"
    POINT_END = "point-end"
    MATCH_END = "match-end"


class Response(StrEnum):
    FOLD = "fold"
    ACCEPT = "accept"
    RAISE = "raise"


class TalkAction(StrEnum):
    SEND = "send"
    LISTEN = "listen"
    SPY = "spy"
    BLUFF = "bluff"
    NOTHING = "nothing"


class Source(StrEnum):
    """Where an announcement came from (How the Agents Decide 3.3: four sources)."""

    PARTNER_SIGNAL = "partner-signal"  # signal from my partner in the talk window
    SPIED_SIGNAL = "spied-signal"  # opponent's signal (or bluff) I intercepted
    DECLARATION = "declaration"  # public declaration before answering a call
    CALL = "call"  # asking for truco counts as announcing CALL_ANNOUNCES


# ============================================================================
# Table (Specification 3)
# ============================================================================

class TablePhase(StrEnum):
    """Names of the states in the table's state machine."""

    START_POINT = "START_POINT"
    TURN = "TURN"
    DECLARE = "DECLARE"
    AWAIT_ANSWER = "AWAIT_ANSWER"
    END_ROUND = "END_ROUND"
    END_POINT = "END_POINT"
    END_MATCH = "END_MATCH"


# ============================================================================
# Decision recipe, the same for everyone (How the Agents Decide 3 and Appendix A)
# ============================================================================

# team_strength = OWN_HAND_WEIGHT × hand_strength + (1 − OWN_HAND_WEIGHT) × partner_belief
OWN_HAND_WEIGHT = 0.7

# chance = 0.5 + CARD_COEFFICIENT × (1 − p) × (team_strength − threat)
#              + p × advantage + ROUND_BALANCE_WEIGHT × round_balance
CARD_COEFFICIENT = 1.3
ROUND_BALANCE_WEIGHT = 0.15

# Added to both thresholds: when ahead on the score, play more conservatively
ADVANTAGE_WEIGHT_IN_THRESHOLDS = 0.08

# Minimum chance for accepting to be worth more than folding, per value called (3.5)
BREAK_EVEN: dict[int, float] = {3: 0.333, 6: 0.250, 9: 0.167, 12: 0.125}

# Bounds of the guess about another player's hand (the queen's power up to the max)
MIN_GUESS = 0.027
MAX_GUESS = 1.0

NOT_LISTENING_FACTOR = 0.7  # trust in the partner for whoever did not choose "listen"
CALL_ANNOUNCES = Category.MEDIUM  # calling truco counts as announcing this (Specification 6.4)


# ============================================================================
# Special personality rules (How the Agents Decide 3.3, 3.4 and 4)
# ============================================================================

LOOSE_CANNON_BIAS_PER_ADVANTAGE = -0.20  # bias about opponents = this × advantage
GRINDER_THREAT_TRUST = 0.65  # the Grinder only listens to opponents when it is a threat

# Maverick's fold bonus: WEIGHT × (folds + INITIAL_FOLDS) / (calls + INITIAL_CALLS)
FOLD_BONUS_WEIGHT = 0.2
FOLD_BONUS_INITIAL_FOLDS = 1
FOLD_BONUS_INITIAL_CALLS = 2


# ============================================================================
# Personalities (How the Agents Decide 4)
# ============================================================================

class OpeningWeights(NamedTuple):
    """Chance (%) of opening the round with the strong, the middle or the weak card."""

    strong: float
    medium: float
    weak: float


@dataclass(frozen=True)
class Personality:
    """A personality's knobs. The recipe is the same; only these numbers change."""

    opponent_bias: float  # how much it overestimates (+) or underestimates (−) opponents
    partner_bias: float
    trust: float  # how much it believes an announcement (0 to 1)
    score_weight: float  # the "p": how much the score takes the place of the cards
    caution: float  # added to the break-even point to fold
    raise_base: float  # minimum chance to call or raise
    opening_3: OpeningWeights | None  # None = fixed rule (Rational Shark)
    opening_2: OpeningWeights | None  # with 2 cards there is no "medium"
    talk: dict[TalkAction, float]  # % of each action in the talk window
    spy_success: float


RATIONAL_SHARK = Personality(
    opponent_bias=0.0,
    partner_bias=0.0,
    trust=0.70,
    score_weight=0.0,
    caution=0.0,
    raise_base=0.68,
    opening_3=None,
    opening_2=None,
    talk={
        TalkAction.SEND: 30,
        TalkAction.LISTEN: 30,
        TalkAction.SPY: 20,
        TalkAction.BLUFF: 5,
        TalkAction.NOTHING: 15,
    },
    spy_success=0.50,
)

MAVERICK_BLUFFER = Personality(
    opponent_bias=0.0,
    partner_bias=0.0,
    trust=0.40,
    score_weight=0.0,
    caution=0.0,
    raise_base=0.62,
    opening_3=OpeningWeights(strong=70, medium=20, weak=10),
    opening_2=OpeningWeights(strong=85, medium=0, weak=15),
    talk={
        TalkAction.SEND: 20,
        TalkAction.LISTEN: 10,
        TalkAction.SPY: 25,
        TalkAction.BLUFF: 35,
        TalkAction.NOTHING: 10,
    },
    spy_success=0.70,
)

LOOSE_CANNON = Personality(
    opponent_bias=0.0,  # its bias depends on the score: LOOSE_CANNON_BIAS_PER_ADVANTAGE
    partner_bias=0.0,
    trust=0.85,
    score_weight=0.4,
    caution=-0.05,
    raise_base=0.58,
    opening_3=OpeningWeights(strong=33, medium=34, weak=33),
    opening_2=OpeningWeights(strong=50, medium=0, weak=50),
    talk={
        TalkAction.SEND: 30,
        TalkAction.LISTEN: 20,
        TalkAction.SPY: 25,
        TalkAction.BLUFF: 15,
        TalkAction.NOTHING: 10,
    },
    spy_success=0.45,
)

GRINDER = Personality(
    opponent_bias=0.15,
    partner_bias=-0.10,
    trust=0.80,  # partner only; with opponents: GRINDER_THREAT_TRUST or 0
    score_weight=0.0,
    caution=0.10,
    raise_base=0.75,
    opening_3=OpeningWeights(strong=10, medium=25, weak=65),
    opening_2=OpeningWeights(strong=15, medium=0, weak=85),
    talk={
        TalkAction.SEND: 20,
        TalkAction.LISTEN: 40,
        TalkAction.SPY: 10,
        TalkAction.BLUFF: 5,
        TalkAction.NOTHING: 25,
    },
    spy_success=0.25,
)
