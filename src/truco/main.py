"""Ponto de entrada. Por enquanto só roda um agente one-shot de teste."""

import asyncio
import spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour

from truco.config import AGENT_PASSWORD, XMPP_DOMAIN


class MeuComportamento(OneShotBehaviour):
    agent: Agent


    async def on_start(self) -> None:
        print("Iniciando comportamento one-shot de teste.")

    async def run(self) -> None:
        print("Comportamento one-shot de teste rodando.")
        await asyncio.sleep(1)
        print("Comportamento one-shot de teste finalizado.")

    async def on_end(self) -> None:
        print("Comportamento one-shot de teste encerrado.")
        await self.agent.stop()



class MeuAgente(Agent):
    async def setup(self) -> None:
        print(f"[{self.jid}] Configurando agente.")

        self.comportamento = MeuComportamento()
        self.add_behaviour(self.comportamento)


async def main():
    id = f"meu_agente@{XMPP_DOMAIN}"

    agente = MeuAgente(id, AGENT_PASSWORD)

    await agente.start()
    print(f"[{id}] Agente iniciado.")

    while agente.is_alive():
        try:
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("Interrompido pelo usuário.")
            break

    assert agente.comportamento.exit_code == 10
    await agente.stop()

    print(f"[{id}] Agente encerrado.")


def run() -> None:
    spade.run(main(), embedded_xmpp_server=True)

if __name__ == "__main__":
    run()
