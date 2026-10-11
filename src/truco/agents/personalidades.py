"""As quatro personalidades deliberativas (Como os Agentes Decidem, Seção 4).

Cada uma só aponta para os seus botões em truco.config e, se tiver regra
especial, sobrescreve um gancho.
"""

from truco import config
from truco.bdi import JogadorBDI
from truco.config import Categoria
from truco.jogo import Carta


class RationalShark(JogadorBDI):
    personalidade = config.RATIONAL_SHARK

    def abrir_rodada(self) -> Carta:
        """Regra fixa: a mais forte se o poder dela supera a ameaça, senão a mais fraca."""
        raise NotImplementedError


class MaverickBluffer(JogadorBDI):
    personalidade = config.MAVERICK_BLUFFER

    def bonus_pedido(self) -> float:
        """BONUS_FUGA_* aplicados ao histórico de quem responderia ao meu pedido."""
        raise NotImplementedError


class LooseCannon(JogadorBDI):
    personalidade = config.LOOSE_CANNON

    def vies(self, jogador: str) -> float:
        """Sobre adversários: LOOSE_CANNON_VIES_POR_VANTAGEM × vantagem."""
        raise NotImplementedError


class Grinder(JogadorBDI):
    personalidade = config.GRINDER

    def confianca(self, emissor: str, categoria: Categoria, fonte: str) -> float:
        """Parceiro: a confiança normal. Adversário: GRINDER_CONFIANCA_AMEACA se for ameaça
        (anúncio forte ou pedido), senão 0."""
        raise NotImplementedError
