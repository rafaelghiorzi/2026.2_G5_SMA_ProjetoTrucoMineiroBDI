"""Ponto de entrada SPADE do Truco Mineiro.

Por enquanto só sobe o servidor XMPP embutido e roda um agente one-shot
para validar o ambiente.
"""

import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour

from truco.config import AGENT_PASSWORD, jid


class HelloAgent(Agent):
    class SayHello(OneShotBehaviour):
        async def run(self) -> None:
            print(f"[{self.agent.jid}] Olá! Ambiente SPADE funcionando.")
            await self.agent.stop()

    async def setup(self) -> None:
        self.add_behaviour(self.SayHello())


async def main() -> None:
    agent = HelloAgent(jid("hello"), AGENT_PASSWORD)
    await agent.start()
    await spade.wait_until_finished(agent)


def run() -> None:
    spade.run(main(), embedded_xmpp_server=True)


if __name__ == "__main__":
    run()
