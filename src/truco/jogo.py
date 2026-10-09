import random
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import mean
from typing import Literal

CARTAS = Literal["Q", "J", "K", "A", "2", "3", "CR", "7O", "AE", "7C", "4P"]
TIME = Literal["A", "B"]
NIVEIS_APOSTA = [1, 3, 6, 9, 12]
POSICAO_MANILHA = 8  # 7O, AE, 7C e 4P

# Faixas de força da mão
LIMITE_FRACA = 0.35
LIMITE_FORTE = 0.60

POSICOES: dict[str, int] = {
    "Q" : 1,
    "J" : 2,
    "K" : 3,
    "A" : 4,
    "2" : 5,
    "3" : 6,
    "CR" : 7,    # Curinga
    "7O" : 8,    # 7 de Ouros
    "AE" : 9,    # A de Espadas
    "7C" : 10,   # 7 de Copas
    "4P" : 11    # 4 de Paus (Zap!)
}

QUANTIDADES: dict[CARTAS, int] = {
    "Q" : 4,
    "J" : 4,
    "K" : 4,
    "A" : 3,
    "2" : 4,
    "3" : 4,
    "CR" : 2,    # Curinga
    "7O" : 1,    # 7 de Ouros
    "AE" : 1,    # A de Espadas
    "7C" : 1,   # 7 de Copas
    "4P" : 1    # 4 de Paus (Zap!)
}

def time_de(jogadores: list[str], jogador: str) -> TIME:

    """Assentos alternam os times: 1º e 3º são o A, 2º e 4º são o B."""
    return "A" if jogadores.index(jogador) % 2 == 0 else "B"

@dataclass(frozen=True)
class Carta:
    valor: CARTAS

    @property
    def posicao(self) -> int:
        return POSICOES[self.valor]

    @property
    def poder(self) -> float:
        return (self.posicao / 11) ** 1.5

    @property
    def manilha(self) -> bool:
        return self.posicao >= POSICAO_MANILHA


class Categoria(StrEnum):
    """Categoria da mão, usada em sinais e declarações (Como os Agentes Decidem 3.2)."""

    FRACA = "fraca"
    MEDIA = "media"
    FORTE = "forte"

def categoria_de(forca: float) -> Categoria:
    """Separada da Mao porque o BDI também classifica a força de quem já jogou tudo."""
    if forca < LIMITE_FRACA:
        return Categoria.FRACA
    if forca < LIMITE_FORTE:
        return Categoria.MEDIA
    return Categoria.FORTE

@dataclass
class Mao:
    """As cartas que um jogador ainda tem."""

    cartas: list[Carta] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.cartas)

    def __iter__(self) -> Iterator[Carta]:
        return iter(self.cartas)

    def __contains__(self, carta: Carta) -> bool:
        return carta in self.cartas

    def remover(self, carta: Carta) -> None:
        """Tira uma cópia da carta. Erro se ela não estiver na mão."""
        self.cartas.remove(carta)

    @property
    def forca(self) -> float:
        """Média do poder das cartas. Erro se a mão estiver vazia."""
        return mean(carta.poder for carta in self.cartas)

    @property
    def categoria(self) -> Categoria:
        return categoria_de(self.forca)

    @property
    def tem_manilha(self) -> bool:
        return any(carta.manilha for carta in self.cartas)

    def mais_forte(self) -> Carta:
        return max(self.cartas, key=lambda carta: carta.posicao)

    def mais_fraca(self) -> Carta:
        return min(self.cartas, key=lambda carta: carta.posicao)

    def mais_fraca_que_vence(self, alvo: Carta) -> Carta | None:
        """A carta mais fraca que ganha de `alvo`, ou None se nenhuma ganha."""
        vencedoras = [carta for carta in self.cartas if carta.posicao > alvo.posicao]
        return min(vencedoras, key=lambda carta: carta.posicao, default=None)


@dataclass
class Baralho:
    cartas: list[Carta] = field(init=False)
    rng: random.Random  = field(default_factory=random.Random)

    def __post_init__(self):
        self.cartas = self.gerar_baralho()

    def gerar_baralho(self) -> list[Carta]:
        """Cria a quantidade certa de cada carta"""
        baralho = []
        for valor, quantidade in QUANTIDADES.items():
            baralho.extend([Carta(valor)] * quantidade)

        return baralho

    def embaralhar(self) -> None:
        """Embaralha o baralho"""
        self.rng.shuffle(self.cartas)

    def distribuir(self, jogadores: list[str]) -> dict[str, Mao]:
        """
        Recebe a lista de JIDs dos agentes jogadores
        Devolve um dicionário jogador -> lista
        """
        maos = {}
        for jogador in jogadores:
            maos[jogador] = Mao([self.cartas.pop() for _ in range(3)])
        return maos


# Uma rodada na mesa: (jogador, carta) na ordem em que foram jogadas
CartasNaMesa = list[tuple[str, Carta]]

@dataclass
class Ponto:
    """
    Um ponto: melhor de 3 rodadas

    Lista de jogadores vem na ordem A-B-A-B. A mesa cria um Ponto novo a cada ponto.
    """
    jogadores: list[str]
    resultados: list[TIME | None] = field(default_factory=list)  # None = empate

    def vencedor_rodada(self, cartas_na_mesa: CartasNaMesa) -> TIME | None:
        """Time da carta mais alta. Se as mais altas forem de times diferentes, empate (None)."""

        maior = max(carta.posicao for _, carta in cartas_na_mesa)
        times: set[TIME] = {
            time_de(self.jogadores, jogador)
            for jogador, carta in cartas_na_mesa
            if carta.posicao == maior
        }

        if len(times) == 1:
            return next(iter(times))
        return None

    def registrar_rodada(self, cartas_na_mesa: CartasNaMesa) -> TIME | None:
        """Decide a rodada e guarda o resultado."""
        vencedor = self.vencedor_rodada(cartas_na_mesa)
        self.resultados.append(vencedor)
        return vencedor

    def quem_comeca(self, cartas_na_mesa: CartasNaMesa) -> str:
        """
        Quem venceu começa. Se os parceiros empataram 
        na carta vencedora, começa quem jogou primeiro.
        Se a rodada empatou, abre de novo quem abriu ela
        """

        vencedor = self.vencedor_rodada(cartas_na_mesa)
        if vencedor is None:
            return cartas_na_mesa[0][0] # retorna o primeiro jogador
        
        maior = max(carta.posicao for _, carta in cartas_na_mesa)
        for jogador, carta in cartas_na_mesa:
            if carta.posicao == maior and time_de(self.jogadores, jogador) == vencedor:
                return jogador

        raise AssertionError("inalcançável")

    def _decisao(self) -> tuple[bool, TIME | None]:
        """
        Define o vencedor da rodada, ou None se não tiver ganhadores
        """
        
        resultados = self.resultados
        
        for time in ("A", "B"):
            if resultados.count(time) >= 2:
                return True, time
        
        if not resultados:
            return False, None
        
        if resultados[0] is None:
            # 1ª empatou: vence o primeiro que ganhar uma rodada depois
            for resultado in resultados[1:]:
                if resultado is not None:
                    return True, resultado

            # 3 empates retorna None, ninguém ganhou    
            return len(resultados) == 3, None
        
        # 1ª teve vencedor: empate na 2ª ou na 3ª dá o ponto para ele
        if None in resultados[1:]:
            return True, resultados[0]

        # 1ª e 2ª com vencedores diferentes, continua jogo
        return False, None
    
    @property
    def encerrada(self) -> bool:
        return self._decisao()[0]

    def vencedor_ponto(self) -> TIME | None:
        """Só faz sentido com o ponto encerrado. None = ninguém pontua."""
        return self._decisao()[1]


@dataclass
class Aposta:
    """
    Fluxo: pedir() abre um pedido pendente; quem responde chama aceitar(), correr()
    ou aumentar(). Aumentar é aceitar o nível atual e pedir o seguinte.
    """

    jogadores: list[str]
    valor: int = 1                      # quanto o ponto vale agora
    pendente: int | None = None         # valor pedido, esperando resposta
    quem_pediu: str | None = None
    ultimo_time: TIME | None = None     # quem fez o último aumento (regra 7)

    def _proximo_nivel(self) -> int | None:
        atual = self.pendente if self.pendente is not None else self.valor
        i = NIVEIS_APOSTA.index(atual)
        return NIVEIS_APOSTA[i + 1] if i + 1 < len(NIVEIS_APOSTA) else None

    def pode_pedir(self, jogador: str, rodada: int) -> bool:
        """
        Vale para pedir na vez e para aumentar ao responder.
        A mesa ainda confere se é a vez dele (regra 2) ou se é ele quem responde.
        """
        return (
            rodada >= 2
            and self._proximo_nivel() is not None
            and time_de(self.jogadores, jogador) != self.ultimo_time
        )

    def quem_responde(self, jogador_que_pediu: str) -> str:
        """O próximo na ordem de jogo, que é sempre do outro time."""
        i = self.jogadores.index(jogador_que_pediu)
        return self.jogadores[(i + 1) % len(self.jogadores)]

    def pedir(self, jogador: str) -> int:
        """Abre o pedido e devolve o valor pedido. Validar antes com pode_pedir."""
        nivel = self._proximo_nivel()
        assert nivel is not None
        self.pendente = nivel
        self.quem_pediu = jogador
        self.ultimo_time = time_de(self.jogadores, jogador)
        return nivel

    def aceitar(self) -> None:
        assert self.pendente is not None
        self.valor = self.pendente
        self.pendente = None

    def correr(self) -> tuple[TIME, int]:
        """Encerra o ponto: quem pediu leva o valor de antes do pedido."""
        assert self.pendente is not None and self.quem_pediu is not None
        self.pendente = None
        return time_de(self.jogadores, self.quem_pediu), self.valor

    def aumentar(self, jogador: str) -> int:
        """Aceita o pedido atual e pede o próximo nível."""
        self.aceitar()
        return self.pedir(jogador)
