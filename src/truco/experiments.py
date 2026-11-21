"""Experimental conditions: which version of each change to the personalities is in use.

    original     as in the first batch (results/events.csv): truco call announces a strong
                 hand, first versions of Grinder, Rational Shark, Loose Cannon and Madman
    anuncio      only the fix of the announcement: a call counts as a medium hand
    recalibrado  every change: announcement, Madman, Grinder, Rational Shark and Loose Cannon

apply(name) changes config and the behaviour classes before the matches are created.
"""

from truco import config
from truco.agents.control import Madman
from truco.agents.player import Grinder, LooseCannon, RationalShark

CONDITIONS: dict[str, dict] = {
    "original": dict(
        call_strength=config.CATEGORY_VALUE[config.Category.STRONG],
        madman_counts_dealt_manilha=False,
        grinder=config.GRINDER_ORIGINAL,
        shark_models_opponents=False,
        loose_cannon=config.LOOSE_CANNON_ORIGINAL,
        loose_cannon_tilts=False,
    ),
    "anuncio": dict(
        call_strength=config.CATEGORY_VALUE[config.Category.MEDIUM],
        madman_counts_dealt_manilha=False,
        grinder=config.GRINDER_ORIGINAL,
        shark_models_opponents=False,
        loose_cannon=config.LOOSE_CANNON_ORIGINAL,
        loose_cannon_tilts=False,
    ),
    "recalibrado": dict(
        call_strength=config.CATEGORY_VALUE[config.Category.MEDIUM],
        madman_counts_dealt_manilha=True,
        grinder=config.GRINDER,
        shark_models_opponents=True,
        loose_cannon=config.LOOSE_CANNON,
        loose_cannon_tilts=True,
    ),
}


def apply(name: str) -> None:
    """Puts the condition in place. Error if the name is unknown."""
    if name not in CONDITIONS:
        raise ValueError(f"unknown condition {name!r}: use one of {', '.join(CONDITIONS)}")
    c = CONDITIONS[name]
    config.CALL_STRENGTH = c["call_strength"]
    Madman.counts_dealt_manilha = c["madman_counts_dealt_manilha"]
    Grinder.personality = c["grinder"]
    RationalShark.models_opponents = c["shark_models_opponents"]
    LooseCannon.personality = c["loose_cannon"]
    LooseCannon.tilts = c["loose_cannon_tilts"]


def results_file(name: str) -> str:
    """results/events.csv -> results/events_<name>.csv"""
    base, dot, ext = config.RESULTS_FILE.rpartition(".")
    return f"{base}_{name}{dot}{ext}"
