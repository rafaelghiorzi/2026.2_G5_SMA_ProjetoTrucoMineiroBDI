"""
One log file per match. Agents only call the logger; this file decides where it goes.
"""

import logging
from pathlib import Path
from datetime import datetime

from truco.config import MATCH_LOG_DIR

FORMAT = logging.Formatter("%(asctime)s %(levelname)-7s %(name)-14s %(message)s", "%H:%M:%S")

logging.getLogger("truco").setLevel(logging.DEBUG)
logging.getLogger("truco").propagate = False

def setup_console() -> None:
    """
    Terminal: only the narration (INFO and above), never the raw messages.
    """
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(FORMAT)
    logging.getLogger("truco").addHandler(console)

def open_match_log(seed: int | None) -> logging.Handler:
    """
    File: everything from the game, including raw messages, plus SPADE's warnings and errors.
    """
    folder = Path(MATCH_LOG_DIR)
    folder.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    handler = logging.FileHandler(folder / f"{stamp}_seed{seed}.log", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(FORMAT)
    logging.getLogger("truco").addHandler(handler)
    logging.getLogger("spade").addHandler(handler)
    return handler

def close_match_log(handler: logging.Handler) -> None:
    logging.getLogger("truco").removeHandler(handler)
    logging.getLogger("spade").removeHandler(handler)
    handler.close()