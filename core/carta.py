NAIPES = ["ouros", "espadas", "copas", "paus"]

# Ordem normal, da mais fraca para a mais forte (o índice casa com a lógica de força da carta)
ORDEM_NORMAL = ["4", "5", "6", "7", "Q", "J", "K", "A", "2", "3"]

# Manilhas fixas, da mais forte para a mais fraca
MANILHAS_FIXAS_ORDEM = [
    ("4", "paus"),     # Zap — mais forte do jogo
    ("7", "copas"),
    ("A", "espadas"),  # Espadilha
    ("7", "ouros"),    # mais fraca das manilhas
]

from dataclasses import dataclass

@dataclass(frozen=True)
class Carta:
    valor: str
    naipe: str

def __post_init__(self):
    if self.valor not in ORDEM_NORMAL:
        raise ValueError(f"Valor inválido: {self.valor}")
    if self.naipe not in NAIPES:
        raise ValueError(f"Naipe inválido: {self.naipe}")

@property
def eh_manilha(self) -> bool:
    return (self.valor, self.naipe) in MANILHAS_FIXAS_ORDEM

def forca(self) -> int:
    if self.eh_manilha:
        posicao = MANILHAS_FIXAS_ORDEM.index((self.valor, self.naipe))
        return 15 - posicao
    return ORDEM_NORMAL.index(self.valor)

def comparar_cartas(c1: Carta, c2: Carta) -> int:
    f1, f2 = c1.forca(), c2.forca()
    if f1 > f2:
        return 1
    if f1 < f2:
        return -1
    return 0
