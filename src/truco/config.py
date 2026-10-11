"""Configuração central: todo dado que o jogo e os agentes usam mora aqui.

Este módulo não importa nada do projeto nem do SPADE, então qualquer arquivo
pode importá-lo sem criar ciclos. As seções seguem os documentos em docs/.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, NamedTuple


# ============================================================================
# Sistema
# ============================================================================

# Servidor XMPP embutido do SPADE
XMPP_DOMAIN = "localhost"
AGENT_PASSWORD = "truco"

ONTOLOGIA = "truco-mineiro"
TEMPO_DE_JOGADA = 15  # segundos esperando uma jogada antes de pedir de novo


# ============================================================================
# Cartas (Especificação 2.1)
# ============================================================================

class Valor(StrEnum):
    """Os 11 valores de carta. O texto é o código que viaja nas mensagens."""

    DAMA = "Q"
    VALETE = "J"
    REI = "K"
    AS = "A"
    DOIS = "2"
    TRES = "3"
    CURINGA = "CR"
    SETE_DE_OUROS = "7O"
    AS_DE_ESPADAS = "AE"
    SETE_DE_COPAS = "7C"
    ZAP = "4P"  # 4 de paus


class InfoCarta(NamedTuple):
    posicao: int  # quem ganha de quem: maior posição vence
    copias: int  # quantas existem no baralho


CARTAS: dict[Valor, InfoCarta] = {
    Valor.DAMA: InfoCarta(posicao=1, copias=4),
    Valor.VALETE: InfoCarta(posicao=2, copias=4),
    Valor.REI: InfoCarta(posicao=3, copias=4),
    Valor.AS: InfoCarta(posicao=4, copias=3),  # o quarto A é o de espadas
    Valor.DOIS: InfoCarta(posicao=5, copias=4),
    Valor.TRES: InfoCarta(posicao=6, copias=4),
    Valor.CURINGA: InfoCarta(posicao=7, copias=2),
    Valor.SETE_DE_OUROS: InfoCarta(posicao=8, copias=1),
    Valor.AS_DE_ESPADAS: InfoCarta(posicao=9, copias=1),
    Valor.SETE_DE_COPAS: InfoCarta(posicao=10, copias=1),
    Valor.ZAP: InfoCarta(posicao=11, copias=1),
}

POSICAO_MANILHA = 8  # da posição 8 em diante é manilha
POSICAO_MAXIMA = max(info.posicao for info in CARTAS.values())
EXPOENTE_PODER = 1.5  # poder = (posição / máxima) ** expoente (Como os Agentes Decidem 3.1)
CARTAS_POR_MAO = 3


# ============================================================================
# Times, pontuação e aposta (Especificação 2.4)
# ============================================================================

TIME = Literal["A", "B"]
TIMES: tuple[TIME, TIME] = ("A", "B")

PONTOS_PARA_VENCER = 12
NIVEIS_APOSTA = [1, 3, 6, 9, 12]  # sem pedido, truco, seis, nove, doze
RODADA_MINIMA_PARA_PEDIR = 2


# ============================================================================
# Categoria da mão (Como os Agentes Decidem 3.2 e 3.3)
# ============================================================================

class Categoria(StrEnum):
    """Categoria da mão, usada em sinais e declarações."""

    FRACA = "fraca"
    MEDIA = "media"
    FORTE = "forte"


LIMITE_FRACA = 0.35  # força abaixo disso: fraca
LIMITE_FORTE = 0.60  # força a partir disso: forte

# Força que cada categoria anunciada representa para quem ouve
VALOR_DA_CATEGORIA: dict[Categoria, float] = {
    Categoria.FRACA: 0.2,
    Categoria.MEDIA: 0.5,
    Categoria.FORTE: 0.8,
}


# ============================================================================
# Protocolo FIPA-ACL (Especificação 6)
# ============================================================================

class Performativa(StrEnum):
    INFORM = "inform"
    REQUEST = "request"
    PROPOSE = "propose"
    ACEITAR = "accept-proposal"
    RECUSAR = "reject-proposal"


class Evento(StrEnum):
    """O que circula entre mesa e jogadores. Os que pedem resposta estão marcados."""

    NOVO_PONTO = "novo-ponto"
    SUA_VEZ = "sua-vez"  # pede: pedir? + carta
    CARTA_JOGADA = "carta-jogada"
    PEDIDO = "pedido"  # pede resposta, se for para mim
    PEDE_DECLARACAO = "pede-declaracao"  # pede: categoria da mão
    DECLARACAO = "declaracao"
    RESPOSTA = "resposta"  # alguém correu, aceitou ou aumentou
    JANELA_CONVERSA = "janela-conversa"  # pede: ação de conversa
    FIM_RODADA = "fim-rodada"
    FIM_PONTO = "fim-ponto"
    FIM_PARTIDA = "fim-partida"


class Resposta(StrEnum):
    CORRER = "correr"
    ACEITAR = "aceitar"
    AUMENTAR = "aumentar"


class AcaoConversa(StrEnum):
    ENVIAR = "enviar"
    RECEBER = "receber"
    ESPIONAR = "espionar"
    BLEFAR = "blefar"
    NADA = "nada"


# ============================================================================
# Mesa (Especificação 3)
# ============================================================================

class FaseDaMesa(StrEnum):
    """Nomes dos estados da máquina de estados da mesa."""

    INICIO_PONTO = "INICIO_PONTO"
    VEZ = "VEZ"
    FIM_RODADA = "FIM_RODADA"
    FIM_PONTO = "FIM_PONTO"
    FIM_PARTIDA = "FIM_PARTIDA"


# ============================================================================
# Receita de decisão, igual para todos (Como os Agentes Decidem 3 e Apêndice A)
# ============================================================================

# força_time = PESO_MINHA_MAO × força_mão + (1 − PESO_MINHA_MAO) × crença_parceiro
PESO_MINHA_MAO = 0.7

# chance = 0,5 + COEFICIENTE_CARTAS × (1 − p) × (força_time − ameaça)
#              + p × vantagem + PESO_SALDO_RODADAS × saldo
COEFICIENTE_CARTAS = 1.3
PESO_SALDO_RODADAS = 0.15

# Somado às duas barras: à frente no placar, fica mais conservador
PESO_VANTAGEM_NAS_BARRAS = 0.08

# Chance mínima para aceitar valer mais que correr, por valor pedido (3.5)
PONTO_DE_EQUILIBRIO: dict[int, float] = {3: 0.333, 6: 0.250, 9: 0.167, 12: 0.125}

# Limites do palpite sobre a mão de outro jogador (o poder da Q até o máximo)
PALPITE_MINIMO = 0.027
PALPITE_MAXIMO = 1.0

FATOR_SEM_RECEBER = 0.7  # confiança no parceiro de quem não escolheu "receber"
CATEGORIA_DO_PEDIDO = Categoria.MEDIA  # pedir truco conta como anúncio disto (Especificação 6.4)


# ============================================================================
# Regras especiais de personalidade (Como os Agentes Decidem 3.3, 3.4 e 4)
# ============================================================================

LOOSE_CANNON_VIES_POR_VANTAGEM = -0.20  # viés sobre adversários = isto × vantagem
GRINDER_CONFIANCA_AMEACA = 0.65  # Grinder só ouve o adversário quando é ameaça

# Bônus de fuga do Maverick: PESO × (fugas + FUGAS_INICIAIS) / (pedidos + PEDIDOS_INICIAIS)
BONUS_FUGA_PESO = 0.2
BONUS_FUGA_FUGAS_INICIAIS = 1
BONUS_FUGA_PEDIDOS_INICIAIS = 2


# ============================================================================
# Personalidades (Como os Agentes Decidem 4)
# ============================================================================

class PesosAbertura(NamedTuple):
    """Chance (%) de abrir a rodada com a carta forte, a do meio ou a fraca."""

    forte: float
    media: float
    fraca: float


@dataclass(frozen=True)
class Personalidade:
    """Os botões de uma personalidade. A receita é a mesma; só estes números mudam."""

    vies_adversario: float  # quanto superestima (+) ou subestima (−) os adversários
    vies_parceiro: float
    confianca: float  # quanto acredita num anúncio (0 a 1)
    peso_placar: float  # o "p": quanto o placar ocupa o lugar das cartas
    cautela: float  # somada ao ponto de equilíbrio para correr
    base_aumentar: float  # chance mínima para pedir ou aumentar
    abertura_3: PesosAbertura | None  # None = regra fixa (Rational Shark)
    abertura_2: PesosAbertura | None  # com 2 cartas não existe "média"
    conversa: dict[AcaoConversa, float]  # % de cada ação na janela de conversa
    sucesso_espionar: float


RATIONAL_SHARK = Personalidade(
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

MAVERICK_BLUFFER = Personalidade(
    vies_adversario=0.0,
    vies_parceiro=0.0,
    confianca=0.40,
    peso_placar=0.0,
    cautela=0.0,
    base_aumentar=0.62,
    abertura_3=PesosAbertura(forte=70, media=20, fraca=10),
    abertura_2=PesosAbertura(forte=85, media=0, fraca=15),
    conversa={
        AcaoConversa.ENVIAR: 20,
        AcaoConversa.RECEBER: 10,
        AcaoConversa.ESPIONAR: 25,
        AcaoConversa.BLEFAR: 35,
        AcaoConversa.NADA: 10,
    },
    sucesso_espionar=0.70,
)

LOOSE_CANNON = Personalidade(
    vies_adversario=0.0,  # o viés dele depende do placar: LOOSE_CANNON_VIES_POR_VANTAGEM
    vies_parceiro=0.0,
    confianca=0.85,
    peso_placar=0.4,
    cautela=-0.05,
    base_aumentar=0.58,
    abertura_3=PesosAbertura(forte=33, media=34, fraca=33),
    abertura_2=PesosAbertura(forte=50, media=0, fraca=50),
    conversa={
        AcaoConversa.ENVIAR: 30,
        AcaoConversa.RECEBER: 20,
        AcaoConversa.ESPIONAR: 25,
        AcaoConversa.BLEFAR: 15,
        AcaoConversa.NADA: 10,
    },
    sucesso_espionar=0.45,
)

GRINDER = Personalidade(
    vies_adversario=0.15,
    vies_parceiro=-0.10,
    confianca=0.80,  # só com o parceiro; com adversários: GRINDER_CONFIANCA_AMEACA ou 0
    peso_placar=0.0,
    cautela=0.10,
    base_aumentar=0.75,
    abertura_3=PesosAbertura(forte=10, media=25, fraca=65),
    abertura_2=PesosAbertura(forte=15, media=0, fraca=85),
    conversa={
        AcaoConversa.ENVIAR: 20,
        AcaoConversa.RECEBER: 40,
        AcaoConversa.ESPIONAR: 10,
        AcaoConversa.BLEFAR: 5,
        AcaoConversa.NADA: 25,
    },
    sucesso_espionar=0.25,
)
