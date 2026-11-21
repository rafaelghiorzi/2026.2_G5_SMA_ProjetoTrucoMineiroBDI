"""Experimental conditions: which version of each change to the personalities is in use.

    original     as in the first batch (results/events.csv): truco call announces a strong
                 hand, first versions of Grinder, Rational Shark, Loose Cannon and Madman
    anuncio      only the fix of the announcement: a call counts as a medium hand
    recalibrado  every change: announcement, Madman, Grinder, Rational Shark and Loose Cannon
    calib_NNN    calibration for truco: the bluffer stays ahead, by less. A call is heard as a
                 hand of strength NNN/100 (between medium 0.5 and strong 0.8), the Maverick's fold
                 bonus drops to 0.15, the Grinder is back to its first version (the cautious
                 player, natural prey of the bluff), the Rational Shark models its opponents,
                 the Loose Cannon tilts and the Madman is fixed. Short batches: BDI against
                 BDI only, CALIBRATION_GAMES_PER_SIDE per side.

apply(name) changes config and the behaviour classes before the matches are created.
A condition may also set the batch: "bdi_only" (no control players) and "games_per_side".
"""

from truco import config
from truco.agents.control import Madman
from truco.agents.player import Grinder, LooseCannon, RationalShark

# Value from config.py, for every condition that does not set its own
DEFAULT_TILT_BIAS = config.LOOSE_CANNON_TILT_BIAS

CONDITIONS: dict[str, dict] = {
    "original": dict(
        call_strength=config.CATEGORY_VALUE[config.Category.STRONG],
        fold_bonus_weight=0.2,
        madman_counts_dealt_manilha=False,
        grinder=config.GRINDER_ORIGINAL,
        shark_models_opponents=False,
        loose_cannon=config.LOOSE_CANNON_ORIGINAL,
        loose_cannon_tilts=False,
    ),
    "anuncio": dict(
        call_strength=config.CATEGORY_VALUE[config.Category.MEDIUM],
        fold_bonus_weight=0.2,
        madman_counts_dealt_manilha=False,
        grinder=config.GRINDER_ORIGINAL,
        shark_models_opponents=False,
        loose_cannon=config.LOOSE_CANNON_ORIGINAL,
        loose_cannon_tilts=False,
    ),
    "recalibrado": dict(
        call_strength=config.CATEGORY_VALUE[config.Category.MEDIUM],
        fold_bonus_weight=0.2,
        madman_counts_dealt_manilha=True,
        grinder=config.GRINDER,
        shark_models_opponents=True,
        loose_cannon=config.LOOSE_CANNON,
        loose_cannon_tilts=True,
    ),
}

CALIBRATION_STRENGTHS = (0.60, 0.65, 0.70, 0.75)
CALIBRATION_GAMES_PER_SIDE = 10


def truco_setup(call_strength: float) -> dict:
    """The personalities tuned for truco, with a given strength for a truco call."""
    return dict(
        call_strength=call_strength,
        fold_bonus_weight=0.15,
        madman_counts_dealt_manilha=True,
        grinder=config.GRINDER_ORIGINAL,
        shark_models_opponents=True,
        loose_cannon=config.LOOSE_CANNON,
        loose_cannon_tilts=True,
    )


for _strength in CALIBRATION_STRENGTHS:
    CONDITIONS[f"calib_{round(_strength * 100):03d}"] = dict(
        truco_setup(_strength), bdi_only=True, games_per_side=CALIBRATION_GAMES_PER_SIDE
    )


def apply(name: str) -> None:
    """Puts the condition in place. Error if the name is unknown."""
    if name not in CONDITIONS:
        raise ValueError(f"unknown condition {name!r}: use one of {', '.join(CONDITIONS)}")
    c = CONDITIONS[name]
    config.CALL_STRENGTH = c["call_strength"]
    config.FOLD_BONUS_WEIGHT = c["fold_bonus_weight"]
    Madman.counts_dealt_manilha = c["madman_counts_dealt_manilha"]
    Grinder.personality = c["grinder"]
    RationalShark.models_opponents = c["shark_models_opponents"]
    LooseCannon.personality = c["loose_cannon"]
    LooseCannon.tilts = c["loose_cannon_tilts"]
    config.LOOSE_CANNON_TILT_BIAS = c.get("loose_cannon_tilt_bias", DEFAULT_TILT_BIAS)


def results_file(name: str) -> str:
    """results/events.csv -> results/events_<name>.csv"""
    base, dot, ext = config.RESULTS_FILE.rpartition(".")
    return f"{base}_{name}{dot}{ext}"
