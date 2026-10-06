"""Crenças do jogador BDI (Seção 4.1 da especificação)."""

from dataclasses import dataclass, field

from truco.core.carta import Carta
from truco.protocol.performatives import Categoria


@dataclass
class Anuncio:
    """Último anúncio ouvido sobre um jogador (sinal, declaração ou pedido)."""

    categoria: Categoria
    confianca: float  # já ajustada (ex.: x0,7 se não escolheu "receber")


@dataclass
class Crencas:
    eu: str
    parceiro: str
    adversarios: tuple[str, str]

    # Fatos
    minhas_cartas: list[Carta] = field(default_factory=list)
    cartas_jogadas: dict[str, list[Carta]] = field(default_factory=dict)
    mesa_rodada: list[tuple[str, Carta]] = field(default_factory=list)  # (jogador, carta)
    resultados_rodadas: list[str | None] = field(default_factory=list)  # time vencedor / None = empate
    placar: dict[str, int] = field(default_factory=lambda: {"A": 0, "B": 0})
    valor_aposta: int = 1
    ultimo_a_aumentar: str | None = None  # time
    ja_enviei_sinal: bool = False

    # Anúncios (filtrados pela confiança na hora de calcular a crença)
    anuncios: dict[str, Anuncio] = field(default_factory=dict)

    # Única memória entre mãos: jogador -> (fugas, pedidos recebidos)
    historico_fuga: dict[str, tuple[int, int]] = field(default_factory=dict)

    def nova_mao(self, cartas: list[Carta]) -> None:
        """Apaga tudo o que é da mão anterior, exceto placar e histórico de fuga."""
        self.minhas_cartas = list(cartas)
        self.cartas_jogadas = {}
        self.mesa_rodada = []
        self.resultados_rodadas = []
        self.valor_aposta = 1
        self.ultimo_a_aumentar = None
        self.ja_enviei_sinal = False
        self.anuncios = {}
