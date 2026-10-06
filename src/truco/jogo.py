"""Regras do jogo, sem SPADE (Especificação, Seção 2)."""


class Carta:
    def posicao(self) -> int:
        raise NotImplementedError

    def poder(self) -> float:
        raise NotImplementedError


class Baralho:
    def embaralhar(self):
        raise NotImplementedError

    def distribuir(self, jogadores):
        raise NotImplementedError


class Mao:
    """Uma mão: melhor de 3 rodadas."""

    def vencedor_rodada(self, cartas_na_mesa):
        raise NotImplementedError

    def vencedor_mao(self):
        raise NotImplementedError


class Aposta:
    """Truco, seis, nove, doze."""

    def pode_pedir(self, jogador) -> bool:
        raise NotImplementedError

    def quem_responde(self, jogador_que_pediu):
        raise NotImplementedError
