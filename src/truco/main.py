"""Entry point. Initiates a game!"""


import spade
import random
from slixmpp import JID
from truco.config import AGENT_PASSWORD, XMPP_DOMAIN

from truco.agents.table import TableAgent
from truco.agents.blackboard import BlackBoardAgent
from truco.agents.player import Player, LooseCannon, MaverickBluffer, Grinder, RationalShark

SEATS = ["A1", "B1", "A2", "B2"]

async def main():
    players = [JID(f"player_{seat}@{XMPP_DOMAIN}") for seat in SEATS]
    table_jid = JID(f"table@{XMPP_DOMAIN}")
    board_jid = JID(f"board@{XMPP_DOMAIN}")
    personalities = [Grinder, MaverickBluffer, LooseCannon, RationalShark]

    agents: list[Player] = []
    for i, jid in enumerate(players):
        agents.append(Player(
            jid,
            AGENT_PASSWORD,
            "A" if i % 2 == 0 else "B",
            table_jid,
            board_jid,
            players[(i + 2) % 4],                          # parceiro
            [players[(i + 1) % 4], players[(i + 3) % 4]],  # quem joga logo depois vem primeiro
            random.choice(personalities)(),
        ))
    board = BlackBoardAgent(board_jid, AGENT_PASSWORD, table_jid, players, 1)
    table = TableAgent(table_jid, AGENT_PASSWORD, board_jid, players, 67)


    for player in agents:
        await player.start()
    await board.start()
    await table.start()

    await spade.wait_until_finished([table, *agents])
    await board.stop()

def run() -> None:
    spade.run(main(), embedded_xmpp_server=True)

if __name__ == "__main__":
    run()
