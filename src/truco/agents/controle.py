"""Jogadores de controle, sem BDI (Especificação 5.1).

Herdam só o protocolo de Jogador; não têm crenças nem conversa.
"""

from truco.agents.jogador import Jogador
from truco.comunicacao import Resposta
from truco.jogo import Carta


class Medroso(Jogador):
    def deve_pedir(self) -> bool:
        return False

    def responder_pedido(self, valor_pedido: int) -> Resposta:
        return Resposta.CORRER

    def escolher_carta(self) -> Carta:
        raise NotImplementedError  # a mais fraca


class Maluco(Jogador):
    def deve_pedir(self) -> bool:
        raise NotImplementedError  # tem manilha e as regras permitem

    def responder_pedido(self, valor_pedido: int) -> Resposta:
        raise NotImplementedError  # 50% aceitar / 50% aumentar; em 12, aceita

    def escolher_carta(self) -> Carta:
        raise NotImplementedError  # a mais forte
