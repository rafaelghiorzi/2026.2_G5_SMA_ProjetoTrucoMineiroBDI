"""Spectator: receives a copy of what the table, board and players send it and hands it to the hub.

It never sends anything to the game, so it cannot change the match.
"""

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour

from truco.communication import game_template, read_message, sender_of


class Listen(CyclicBehaviour):
    agent: "SpectatorAgent"

    async def run(self) -> None:
        msg = await self.receive(timeout=10)
        if msg is None:
            return
        event, data = read_message(msg)
        await self.agent.hub.publish({"event": event.value, "from": str(sender_of(msg)), **data})


class SpectatorAgent(Agent):
    def __init__(self, jid, password: str, hub) -> None:
        super().__init__(str(jid), password)
        self.hub = hub

    async def setup(self) -> None:
        self.add_behaviour(Listen(), game_template())
