"""The four deliberative personalities (How the Agents Decide, Section 4).

Each one only points at its knobs in truco.config and, if it has a special
rule, overrides a hook.
"""

from statistics import mean

from truco import config
from truco.bdi import BDIPlayer
from truco.config import (
    FOLD_BONUS_INITIAL_CALLS,
    FOLD_BONUS_INITIAL_FOLDS,
    FOLD_BONUS_WEIGHT,
    GRINDER_THREAT_TRUST,
    LOOSE_CANNON_BIAS_PER_ADVANTAGE,
    Category,
    Source,
)
from truco.game import Card


class RationalShark(BDIPlayer):
    personality = config.RATIONAL_SHARK

    def open_round(self) -> Card:
        """Fixed rule: the strongest if its power beats the threat, otherwise the weakest."""
        threat = mean(self.belief_about(opponent) for opponent in self.beliefs.opponents)
        strongest = self.hand.strongest()
        if strongest.power > threat:
            return strongest
        return self.hand.weakest()


class MaverickBluffer(BDIPlayer):
    personality = config.MAVERICK_BLUFFER

    # Against control players the rate is fixed at the neutral value (How the Agents Decide
    # 3.4): a Coward folds every time and would give a bonus that is not skill.
    opponents_are_control: bool = False

    def call_bonus(self) -> float:
        """FOLD_BONUS_* applied to the history of whoever would answer my call."""
        target = self.beliefs.opponents[0]  # plays right after me: answers my call
        folds = 0 if self.opponents_are_control else self.beliefs.folds[target]
        calls = 0 if self.opponents_are_control else self.beliefs.calls_received[target]
        fold_rate = (folds + FOLD_BONUS_INITIAL_FOLDS) / (calls + FOLD_BONUS_INITIAL_CALLS)
        return FOLD_BONUS_WEIGHT * fold_rate


class LooseCannon(BDIPlayer):
    personality = config.LOOSE_CANNON

    def bias(self, player: str) -> float:
        """About opponents: LOOSE_CANNON_BIAS_PER_ADVANTAGE × advantage."""
        if player == self.beliefs.partner:
            return self.personality.partner_bias
        return LOOSE_CANNON_BIAS_PER_ADVANTAGE * self.beliefs.advantage()


class Grinder(BDIPlayer):
    personality = config.GRINDER

    def trust(self, speaker: str, category: Category, source: Source) -> float:
        """Partner: the normal trust. Opponent: GRINDER_THREAT_TRUST if it is a threat
        (strong announcement or call), otherwise 0."""
        if speaker == self.beliefs.partner:
            return self.personality.trust
        if category == Category.STRONG or source == Source.CALL:
            return GRINDER_THREAT_TRUST
        return 0.0
