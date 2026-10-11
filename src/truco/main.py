"""Entry point. For now it only runs a one-shot test agent."""

import asyncio
import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour

from truco.config import AGENT_PASSWORD, XMPP_DOMAIN


class MyBehaviour(OneShotBehaviour):
    agent: Agent


    async def on_start(self) -> None:
        print("Starting one-shot test behaviour.")

    async def run(self) -> None:
        print("One-shot test behaviour running.")
        await asyncio.sleep(1)
        print("One-shot test behaviour finished.")

    async def on_end(self) -> None:
        print("One-shot test behaviour ended.")
        await self.agent.stop()



class MyAgent(Agent):
    async def setup(self) -> None:
        print(f"[{self.jid}] Setting up agent.")

        self.behaviour = MyBehaviour()
        self.add_behaviour(self.behaviour)


async def main():
    id = f"my_agent@{XMPP_DOMAIN}"

    agent = MyAgent(id, AGENT_PASSWORD)

    await agent.start()
    print(f"[{id}] Agent started.")

    while agent.is_alive():
        try:
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Interrupted by the user.")
            break

    assert agent.behaviour.exit_code == 10
    await agent.stop()

    print(f"[{id}] Agent stopped.")


def run() -> None:
    spade.run(main(), embedded_xmpp_server=True)

if __name__ == "__main__":
    run()
