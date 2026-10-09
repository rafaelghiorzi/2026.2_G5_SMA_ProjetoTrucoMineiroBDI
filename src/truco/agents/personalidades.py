"""As quatro personalidades deliberativas (Como os Agentes Decidem, Seção 4).

Cada uma só define os botões e, se tiver regra especial, sobrescreve um gancho.
"""

from truco.bdi import JogadorBDI, Personalidade
from truco.comunicacao import AcaoConversa
from truco.jogo import Carta, Categoria


class RationalShark(JogadorBDI):
    personalidade = Personalidade(
        vies_adversario=0.0,
        vies_parceiro=0.0,
        confianca=0.70,
        peso_placar=0.0,
        cautela=0.0,
        base_aumentar=0.68,
        abertura_3=None,
        abertura_2=None,
        conversa={
            AcaoConversa.ENVIAR: 30,
            AcaoConversa.RECEBER: 30,
            AcaoConversa.ESPIONAR: 20,
            AcaoConversa.BLEFAR: 5,
            AcaoConversa.NADA: 15,
        },
        sucesso_espionar=0.50,
    )

    def abrir_rodada(self) -> Carta:
        """Regra fixa: a mais forte se o poder dela supera a ameaça, senão a mais fraca."""
        raise NotImplementedError


class MaverickBluffer(JogadorBDI):
    personalidade = ...  # TODO: coluna MB

    def bonus_pedido(self) -> float:
        """0,2 × (fugas+1)/(pedidos+2) de quem responderia ao meu pedido."""
        raise NotImplementedError


class LooseCannon(JogadorBDI):
    personalidade = ...  # TODO: coluna LC

    def vies(self, jogador: str) -> float:
        """Sobre adversários: −0,20 × vantagem."""
        raise NotImplementedError


class Grinder(JogadorBDI):
    personalidade = ...  # TODO: coluna GR

    def confianca(self, emissor: str, categoria: Categoria, fonte: str) -> float:
        """Parceiro: 0,80. Adversário: 0,65 se for ameaça (forte ou pedido), senão 0."""
        raise NotImplementedError
