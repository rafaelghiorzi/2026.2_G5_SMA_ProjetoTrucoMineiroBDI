"""Base de todos os jogadores: comunicação com a mesa e ganchos de decisão."""

from spade.agent import Agent


class JogadorAgent(Agent):
    async def setup(self) -> None:
        raise NotImplementedError

    def deve_pedir(self) -> bool:
        raise NotImplementedError

    def responder_pedido(self):
        raise NotImplementedError

    def escolher_carta(self):
        raise NotImplementedError
