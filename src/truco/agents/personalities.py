"""The four deliberative personalities (How the Agents Decide, Section 4).

Each one only points at its knobs in truco.config and, if it has a special
rule, overrides a hook.
"""

from truco import config
from truco.bdi import BDIPlayer
from truco.config import Category
from truco.game import Card


class RationalShark(BDIPlayer):
    personality = config.RATIONAL_SHARK

    def open_round(self) -> Card:
        """Fixed rule: the strongest if its power beats the threat, otherwise the weakest."""
        raise NotImplementedError


class MaverickBluffer(BDIPlayer):
    personality = config.MAVERICK_BLUFFER

    def call_bonus(self) -> float:
        """FOLD_BONUS_* applied to the history of whoever would answer my call."""
        raise NotImplementedError


class LooseCannon(BDIPlayer):
    personality = config.LOOSE_CANNON

    def bias(self, player: str) -> float:
        """About opponents: LOOSE_CANNON_BIAS_PER_ADVANTAGE × advantage."""
        raise NotImplementedError


class Grinder(BDIPlayer):
    personality = config.GRINDER

    def trust(self, speaker: str, category: Category, source: str) -> float:
        """Partner: the normal trust. Opponent: GRINDER_THREAT_TRUST if it is a threat
        (strong announcement or call), otherwise 0."""
        raise NotImplementedError
