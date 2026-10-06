"""Raciocínio dos jogadores deliberativos (Especificação 4; Como os Agentes Decidem 3)."""

from spade.agent import Agent


class Crencas:
    """Fatos vindos da mesa e estimativas sobre a mão dos outros jogadores."""

    def nova_mao(self, cartas):
        raise NotImplementedError


class JogadorBDI(Agent):
    """Ciclo comum às personalidades: perceber -> deliberar -> agir.
    Cada personalidade é uma subclasse com seus próprios parâmetros."""

    async def setup(self) -> None:
        raise NotImplementedError

    def chance_de_vencer(self) -> float:
        raise NotImplementedError

    def deve_pedir(self) -> bool:
        raise NotImplementedError

    def responder_pedido(self):
        raise NotImplementedError

    def escolher_carta(self):
        raise NotImplementedError

    def conversar(self):
        raise NotImplementedError
