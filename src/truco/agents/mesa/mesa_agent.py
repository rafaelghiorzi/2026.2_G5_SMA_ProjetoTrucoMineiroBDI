"""Mesa: árbitro e ambiente (Especificação 3). Agente reativo, não BDI.
O fluxo do jogo é uma máquina de estados (FSMBehaviour)."""

from spade.agent import Agent


class MesaAgent(Agent):
    async def setup(self) -> None:
        raise NotImplementedError
