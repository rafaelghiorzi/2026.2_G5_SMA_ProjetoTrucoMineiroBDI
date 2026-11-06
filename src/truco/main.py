"""Entry point: sets up the agents and plays one match."""

import spade
import random
from slixmpp import JID
from truco.config import AGENT_PASSWORD, XMPP_DOMAIN, THINK_TIME, TEAMS, RESULTS_FILE, SEED, TEAM

from truco.match_log import close_match_log, open_match_log, setup_console
from truco.metrics import MetricsRecorder
from truco.agents.table import TableAgent
from truco.agents.blackboard import BlackboardAgent
from truco.agents.control import ControlBehaviour, Coward, Madman
from truco.agents.player import Player, LooseCannon, MaverickBluffer, Grinder, RationalShark, TrucoBehaviour

SEATS = ["A1", "B1", "A2", "B2"]
PERSONALITIES = [Grinder, MaverickBluffer, LooseCannon, RationalShark]

async def play_match(
        lineup: list[type[TrucoBehaviour]],
        seed: int | None = None,
        think_time: tuple[float, float] | None = THINK_TIME,
        recorder: MetricsRecorder | None = None,
        save_log: bool = True,
) -> dict[TEAM, int]:
    """
    Plays one match and returns the score.

    `lineup` has one behaviour class per seat, in SEATS order. The same `seed` repeats the
    match for the same lineup. `think_time` is the players' delay (None = no delay),
    `recorder` writes the metrics and `save_log` creates the file in match_logs/.
    """

    # The name shows who sits where. XMPP normalizes it to lowercase: maverickbluffer_a1@localhost
    jids = [JID(f"{lineup[i].__name__}_{seat}@{XMPP_DOMAIN}") for i, seat in enumerate(SEATS)]
    table_jid = JID(f"table@{XMPP_DOMAIN}")
    board_jid = JID(f"board@{XMPP_DOMAIN}")
    teams: list[TEAM] = [TEAMS[i % 2] for i in range(4)]

    seeds = random.Random(seed)
    players: list[Player] = []
    for i, jid in enumerate(jids):
        behaviour = lineup[i](rng=random.Random(seeds.randrange(2**32)), think_time=think_time)
        # Maverick's fold bonus stays neutral against control players
        if isinstance(behaviour, MaverickBluffer):
            behaviour.opponents_are_control = issubclass(lineup[(i + 1) % 4], ControlBehaviour)

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
    recorder =  MetricsRecorder(RESULTS_FILE)
    rng = random.Random(SEED)
    
    # To use control personalities, just do
    # Order: A1, B1, A2, B2
    # await play_match([RationalShark, Coward, RationalShark, Coward], SEED, None, recorder)
    
    try:
        await play_match([rng.choice(PERSONALITIES) for _ in SEATS], SEED, THINK_TIME, recorder)
    finally:
        recorder.close()  # even if the match fails, what was measured reaches the file

def run() -> None:
    setup_console()
    spade.run(main(), embedded_xmpp_server=True)

if __name__ == "__main__":
    run()