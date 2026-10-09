"""Raciocínio dos jogadores deliberativos (Especificação 4; Como os Agentes Decidem 3).

Uma receita, vários botões: JogadorBDI implementa a receita uma vez só, e cada
personalidade é uma subclasse que só troca a Personalidade (os botões) e, quando
precisa, sobrescreve um dos três ganchos das regras especiais.
"""

from dataclasses import dataclass

from truco.agents.jogador import Jogador
from truco.comunicacao import AcaoConversa, Categoria, Evento, Resposta
from truco.jogo import Carta


@dataclass(frozen=True)
class Personalidade:
    """Os botões da tabela da Seção 4 de Como os Agentes Decidem."""

    vies_adversario: float
    vies_parceiro: float
    confianca: float
    peso_placar: float
    cautela: float
    base_aumentar: float
    abertura_3: tuple[float, float, float] | None  # forte/média/fraca; None = regra fixa
    abertura_2: tuple[float, float] | None  # forte/fraca
    conversa: dict[AcaoConversa, float]
    sucesso_espionar: float


class Crencas:
    """Só fatos e anúncios brutos. A interpretação (viés, confiança) fica no agente,
    porque depende da personalidade."""

    def novo_ponto(self, cartas: list[Carta]) -> None:
        """Zera tudo que é do ponto. O histórico de fuga sobrevive."""
        raise NotImplementedError

    def registrar_carta(self, jogador: str, carta: Carta) -> None:
        raise NotImplementedError

    def registrar_anuncio(self, sobre: str, categoria: Categoria, fonte: str) -> None:
        """Vale o mais recente por jogador (3.3)."""
        raise NotImplementedError

    def registrar_resposta(self, jogador: str, resposta: Resposta) -> None:
        """Alimenta o histórico de fuga (fugas / pedidos recebidos)."""
        raise NotImplementedError

    def cartas_nao_vistas(self) -> list[Carta]:
        raise NotImplementedError

    def vantagem(self) -> float:
        raise NotImplementedError

    def saldo_rodadas(self) -> int:
        raise NotImplementedError


class JogadorBDI(Jogador):
    personalidade: Personalidade  # cada subclasse define

    async def setup(self) -> None:
        self.crencas = Crencas()
        await super().setup()

    def perceber(self, evento: Evento, dados) -> None:
        """Traduz cada evento em atualização de Crencas.
        Lembrar: PEDIDO também é anúncio de "média" de quem pediu (Especificação 6.4)."""
        raise NotImplementedError

    # --- Receita comum (Como os Agentes Decidem 3.2–3.5, resumo no Apêndice A) ---

    def forca_mao(self) -> float:
        raise NotImplementedError

    def crenca_sobre(self, jogador: str) -> float:
        """Palpite neutro -> + viés -> mistura com anúncio pela confiança."""
        raise NotImplementedError

    def chance_de_vencer(self) -> float:
        raise NotImplementedError

    def barra_correr(self, valor_pedido: int) -> float:
        raise NotImplementedError

    def barra_aumentar(self) -> float:
        raise NotImplementedError

    # --- Decisões (implementam o contrato de Jogador) ---

    def deve_pedir(self) -> bool:
        raise NotImplementedError

    def responder_pedido(self, valor_pedido: int) -> Resposta:
        raise NotImplementedError

    def escolher_carta(self) -> Carta:
        """Última carta / respondendo (regra igual p/ todos) / abrindo (gancho)."""
        raise NotImplementedError

    def declarar(self) -> Categoria:
        raise NotImplementedError

    def conversar(self) -> AcaoConversa:
        """Sorteio com a tabela da personalidade + regras de bom senso (3.7)."""
        raise NotImplementedError

    # --- Ganchos: o padrão lê os botões; personalidades especiais sobrescrevem ---

    def vies(self, jogador: str) -> float:
        raise NotImplementedError

    def confianca(self, emissor: str, categoria: Categoria, fonte: str) -> float:
        """Inclui o ×0,7 de quem não escolheu "receber"."""
        raise NotImplementedError

    def bonus_pedido(self) -> float:
        """Somado à chance só para pedir/aumentar. Padrão: 0."""
        return 0.0

    def abrir_rodada(self) -> Carta:
        """Padrão: sorteio com abertura_3 / abertura_2."""
        raise NotImplementedError
