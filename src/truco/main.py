"""Entry point. Initiates a game!"""

import spade
import random
from typing import Literal, cast
from slixmpp import JID
from truco.config import AGENT_PASSWORD, XMPP_DOMAIN, THINK_TIME, TEAMS

from truco.match_log import close_match_log, open_match_log, setup_console
from truco.metrics import MetricsRecorder
from truco.agents.table import TableAgent
from truco.agents.blackboard import BlackboardAgent
from truco.agents.player import Player, LooseCannon, MaverickBluffer, Grinder, RationalShark, TrucoBehaviour

SEATS = ["A1", "B1", "A2", "B2"]
PERSONALITIES = [Grinder, MaverickBluffer, LooseCannon, RationalShark]
TEAM = Literal["A", "B"]

async def play_match(
        lineup: list[type[TrucoBehaviour]],
        seed: int | None = None,
        think_time: tuple[float, float] | None = THINK_TIME,
        recorder: MetricsRecorder | None = None,
        save_log: bool = True,
) -> dict[TEAM, int]:
    """
    Plays one match and returns the score
    """

    jids = [JID(f"player_{seat}@{XMPP_DOMAIN}") for seat in SEATS]
    table_jid = JID(f"table@{XMPP_DOMAIN}")
    board_jid = JID(f"board@{XMPP_DOMAIN}")
    teams: list[TEAM] = [cast(TEAM, TEAMS[i % 2]) for i in range(4)]

    seeds = random.Random(seed)
    players: list[Player] = []
    for i, jid in enumerate(jids):
        behaviour = lineup[i](rng=random.Random(seeds.randrange(2**32)), think_time=think_time)

        players.append(Player(
            jid, AGENT_PASSWORD, teams[i], table_jid, board_jid,
            jids[(i + 2) % 4],                       # partner
            [jids[(i + 1) % 4], jids[(i + 3) % 4]],  # whoever plays right after me comes first
            behaviour,
        ))

    if recorder is not None:
        recorder.start_match(seed, {jid: (lineup[i].__name__, teams[i]) for i, jid in enumerate(jids)})
    log = open_match_log(seed) if save_log else None

    board = BlackboardAgent(board_jid, AGENT_PASSWORD, table_jid, recorder)
    table = TableAgent(table_jid, AGENT_PASSWORD, board_jid, jids, seed, recorder)
    for player in players:
        await player.start()
    await board.start()
    await table.start()

    await spade.wait_until_finished([table, *players])
    await board.stop()
    if log is not None:
        close_match_log(log)
    return table.score

async def main() -> None:
    await play_match([random.choice(PERSONALITIES) for _ in SEATS])

def run() -> None:
    setup_console()
    spade.run(main(), embedded_xmpp_server=True)

if __name__ == "__main__":
    run()