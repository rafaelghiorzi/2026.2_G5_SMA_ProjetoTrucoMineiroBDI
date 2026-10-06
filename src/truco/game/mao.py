"""Uma mão: melhor de 3 rodadas (Especificação 2.2 e 2.3)."""


class Mao:
    def vencedor_rodada(self, cartas_na_mesa):
        raise NotImplementedError

    def quem_abre_proxima_rodada(self):
        raise NotImplementedError

    def vencedor_mao(self):
        raise NotImplementedError
