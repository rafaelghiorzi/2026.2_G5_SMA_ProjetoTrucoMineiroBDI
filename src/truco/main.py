"""Ponto de entrada. Por enquanto só roda um agente one-shot de teste."""

import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour

from truco.config import AGENT_PASSWORD, XMPP_DOMAIN


class HelloAgent(Agent):
    class SayHello(OneShotBehaviour):
        async def run(self) -> None:
            print(f"[{self.agent.jid}] Olá! Ambiente SPADE funcionando.")
            await self.agent.stop()

    async def setup(self) -> None:
        self.add_behaviour(self.SayHello())


async def main() -> None:
    agent = HelloAgent(f"hello@{XMPP_DOMAIN}", AGENT_PASSWORD)
    await agent.start()
    await spade.wait_until_finished(agent)


def run() -> None:
    spade.run(main(), embedded_xmpp_server=True)


# Obrigatório: o servidor XMPP embutido reimporta __main__ em outro processo.
if __name__ == "__main__":
    run()
