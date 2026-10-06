"""Mesa: árbitro e ambiente (Especificação, Seção 3). Reativa, máquina de estados."""

from spade.agent import Agent
from spade.behaviour import FSMBehaviour


class MesaAgent(Agent):
    class Fluxo(FSMBehaviour):
        pass

    async def setup(self) -> None:
        raise NotImplementedError
