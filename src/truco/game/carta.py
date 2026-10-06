"""Carta e ordem das cartas (Especificação 2.1; Como os Agentes Decidem 3.1)."""


class Carta:
    """Uma carta do baralho de 29 cartas."""

    def posicao(self) -> int:
        """Posição na ordem de força (1 a 11)."""
        raise NotImplementedError

    def poder(self) -> float:
        """Poder da carta entre 0 e 1."""
        raise NotImplementedError

    def eh_manilha(self) -> bool:
        raise NotImplementedError
