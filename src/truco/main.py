"""Entry point: sets up the agents and plays one match."""

import asyncio
import csv
import logging
import random
import sys
from pathlib import Path
from itertools import product

import spade
from slixmpp import JID
from truco.config import AGENT_PASSWORD, XMPP_DOMAIN, THINK_TIME, TEAMS, SEED, TEAM

from truco.match_log import close_match_log, open_match_log, setup_console
from truco.metrics import MetricsRecorder
from truco import experiments
from truco.agents.table import TableAgent
from truco.agents.blackboard import BlackboardAgent
from truco.agents.control import ControlBehaviour, Coward, Madman
from truco.agents.human import Human
from truco.agents.player import Player, LooseCannon, MaverickBluffer, Grinder, RationalShark, TrucoBehaviour

SEATS = ["A1", "B1", "A2", "B2"]
PERSONALITIES = [Grinder, MaverickBluffer, LooseCannon, RationalShark]
CONTROLS = [Coward, Madman]
GAMES_PER_SIDE = 25  # partidas por confronto e por lado (use 1 para um teste rápido)
# Condições rodadas quando nenhuma é passada na linha de comando (ver truco/experiments.py).
# A "original" já foi rodada em 18/11 (results/events.csv), com as mesmas seeds.
DEFAULT_CONDITIONS = ["anuncio", "recalibrado"]


def lineup(team_a, team_b):
    """Ordem dos assentos: A1, B1, A2, B2. Cada dupla tem a mesma personalidade."""
    return [team_a, team_b, team_a, team_b]


async def play_match(
        lineup: list[type[TrucoBehaviour] | TrucoBehaviour],
        seed: int | None = None,
        think_time: tuple[float, float] | None = THINK_TIME,
        recorder: MetricsRecorder | None = None,
        save_log: bool = True,
        spectator: JID | None = None,
        on_setup=None
) -> dict[TEAM, int]:
    """
    Plays one match and returns the score.

    `lineup` has one behaviour class per seat, in SEATS order, or an already built behaviour
    (a Human, which needs the web server). The same `seed` repeats the match for the same lineup. `think_time` is the players' delay (None = no delay),
    `recorder` writes the metrics and `save_log` creates the file in match_logs/.
    """

    kinds = [entry if isinstance(entry, type) else type(entry) for entry in lineup]

    # The name shows who sits where. XMPP normalizes it to lowercase: maverickbluffer_a1@localhost
    jids = [JID(f"{kinds[i].__name__}_{seat}@{XMPP_DOMAIN}") for i, seat in enumerate(SEATS)]
    table_jid = JID(f"table@{XMPP_DOMAIN}")
    board_jid = JID(f"board@{XMPP_DOMAIN}")
    teams: list[TEAM] = [TEAMS[i % 2] for i in range(4)]

    seeds = random.Random(seed)
    players: list[Player] = []
    for i, jid in enumerate(jids):
        rng = random.Random(seeds.randrange(2**32))
        entry = lineup[i]
        if isinstance(entry, TrucoBehaviour):
            behaviour, behaviour.rng = entry, rng
        else:
            behaviour = entry(rng=rng, think_time=think_time)
        # Opponent models (Maverick's fold bonus, Rational Shark's) stay neutral against control players
        if hasattr(behaviour, "opponents_are_control"):
            behaviour.opponents_are_control = issubclass(kinds[(i + 1) % 4], ControlBehaviour)

        players.append(Player(
            jid, AGENT_PASSWORD, teams[i], table_jid, board_jid,
            jids[(i + 2) % 4],                       # partner
            [jids[(i + 1) % 4], jids[(i + 3) % 4]],  # whoever plays right after me comes first
            behaviour,
            spectator=spectator
        ))

    if recorder is not None:
        recorder.start_match(seed, {jid: (kinds[i].__name__, teams[i]) for i, jid in enumerate(jids)})
    log = open_match_log(seed) if save_log else None

    board = BlackboardAgent(board_jid, AGENT_PASSWORD, table_jid, recorder, spectator=spectator)
    humans = {jid for jid, kind in zip(jids, kinds) if issubclass(kind, Human)}
    table = TableAgent(table_jid, AGENT_PASSWORD, board_jid, jids, seed, recorder, spectator=spectator, humans=humans)

    if on_setup is not None:
        await on_setup({"seats": [
            {"jid": str(j), "seat": SEATS[i], "team": teams[i], "personality": kinds[i].__name__,
             "human": j in humans}
            for i, j in enumerate(jids)
        ]})

    agents = [*players, board, table]
    try:
        # Each start registers and connects to the XMPP server: in parallel it takes the time of one.
        # The table goes last, so everyone is already listening when it deals.
        await asyncio.gather(*(agent.start() for agent in agents[:-1]))
        await table.start()
        await spade.wait_until_finished([table, *players])
    finally:
        # Also when the match is cancelled (a new one was asked for): the same JIDs come back
        await asyncio.gather(*(agent.stop() for agent in agents if agent.is_alive()))
        if log is not None:
            close_match_log(log)
    return table.score

async def main() -> None:
    """Roda o lote para cada condição pedida, cada uma no seu CSV.

    Uso: python -m truco.main [condição ...], por exemplo: python -m truco.main anuncio recalibrado
    """
    conditions = sys.argv[1:] or DEFAULT_CONDITIONS
    for name in conditions:  # falha logo se algum nome estiver errado
        experiments.apply(name)
    for name in conditions:
        experiments.apply(name)
        print(f"=== condição {name} -> {experiments.results_file(name)}", flush=True)
        settings = experiments.CONDITIONS[name]
        await run_batch(
            experiments.results_file(name),
            games_per_side=settings.get("games_per_side", GAMES_PER_SIDE),
            with_controls=not settings.get("bdi_only", False),
        )


async def run_batch(results_file: str, games_per_side: int = GAMES_PER_SIDE, with_controls: bool = True) -> None:
    """Todas contra todas e, com with_controls, cada BDI contra cada controle; games_per_side por lado."""
    done_seeds = finished_seeds(results_file)
    if done_seeds:
        print(f"retomando: {len(done_seeds)} partidas já estão em {results_file}", flush=True)
    recorder = MetricsRecorder(results_file)

    # Todas contra todas (BDI) + cada BDI contra cada controle.
    # product já gera (X, Y) e (Y, X): é a troca de lado.
    matchups = [(a, b) for a, b in product(PERSONALITIES, repeat=2) if a is not b]
    if with_controls:
        matchups += [(a, c) for a in PERSONALITIES for c in CONTROLS]
        matchups += [(c, a) for a in PERSONALITIES for c in CONTROLS]

    total = len(matchups) * games_per_side
    done = 0
    seed = SEED
    try:
        for team_a, team_b in matchups:
            for _ in range(games_per_side):
                seed += 1  # uma seed diferente por partida
                done += 1
                if seed in done_seeds:  # já jogada numa execução interrompida
                    continue
                name = f"{team_a.__name__} x {team_b.__name__}"
                try:
                    score = await play_match(
                        lineup(team_a, team_b), seed,
                        think_time=None,   # sem espera artificial
                        recorder=recorder,
                        save_log=False,    # evita gerar milhares de arquivos .log
                    )
                    print(f"[{done}/{total}] seed {seed}: {name} -> {score}", flush=True)
                except Exception as error:
                    # Uma partida que falha não derruba o lote
                    print(f"[{done}/{total}] seed {seed}: {name} FALHOU: {error!r}", flush=True)
    finally:
        recorder.close()  # mesmo se algo falhar, o que foi medido chega ao arquivo


def finished_seeds(results_file: str) -> set[int]:
    """Seeds das partidas que chegaram ao fim (match_end) num CSV de uma execução anterior.

    Uma partida interrompida no meio tem eventos mas não match_end: é jogada de novo. Os
    eventos dela que ficaram no arquivo são descartados na análise (ver analise.py)."""
    file = Path(results_file)
    if not file.exists():
        return set()
    with file.open(newline="", encoding="utf-8") as f:
        return {int(row["seed"]) for row in csv.DictReader(f) if row["event"] == "match_end"}


def run() -> None:
    setup_console()
    # slixmpp avisa a cada mensagem com campo "id"; é inofensivo e enche o terminal
    logging.getLogger().addFilter(lambda record: "Unknown stanza interface" not in record.getMessage())
    spade.run(main(), embedded_xmpp_server=True)

if __name__ == "__main__":
    run()