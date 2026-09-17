
from dataclasses import dataclass

NAIPES = ["ouros", "espadas", "copas", "paus"]
VALORES_NORMAIS = ["Q", "J", "K", "A", "2", "3"]
CURINGA = "curinga"

GAMMA = 1.5  

POSICOES: dict[tuple[str, str | None], int] = {}
for naipe in NAIPES:
    POSICOES[("Q", naipe)] = 1
    POSICOES[("J", naipe)] = 2
    POSICOES[("K", naipe)] = 3
    POSICOES[("2", naipe)] = 5
    POSICOES[("3", naipe)] = 6
POSICOES[("A", "ouros")] = 4
POSICOES[("A", "copas")] = 4
POSICOES[("A", "paus")] = 4
POSICOES[("A", "espadas")] = 9          
POSICOES[(CURINGA, None)] = 7            
POSICOES[("7", "ouros")] = 8
POSICOES[("7", "copas")] = 10
POSICOES[("4", "paus")] = 11           

RHO_MAXIMO = 11


@dataclass(frozen=True)
class Carta:
    valor: str                 
    naipe: str | None = None   

    def __post_init__(self):
        if (self.valor, self.naipe) not in POSICOES:
            raise ValueError(f"Carta inexistente neste baralho: {self.valor} de {self.naipe}")

    @property
    def eh_curinga(self) -> bool:
        return self.valor == CURINGA

    @property
    def eh_manilha(self) -> bool:
        return self.rho() >= 8

    def rho(self) -> int:
        return POSICOES[(self.valor, self.naipe)]

    def poder(self) -> float:
        return (self.rho() / RHO_MAXIMO) ** GAMMA

    def __repr__(self) -> str:
        nome = "Curinga" if self.eh_curinga else f"{self.valor} de {self.naipe}"
        tag = " [MANILHA]" if self.eh_manilha else ""
        return f"{nome}{tag}"


def comparar_cartas(c1: Carta, c2: Carta) -> int:
    r1, r2 = c1.rho(), c2.rho()
    if r1 > r2:
        return 1
    if r1 < r2:
        return -1
    return 0
