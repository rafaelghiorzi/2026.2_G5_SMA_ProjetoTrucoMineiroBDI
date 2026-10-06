"""Quadro da mesa (Especificação 3): placar, cartas jogadas, vencedor de cada
rodada, estado da aposta e ordem de jogo."""


class Quadro:
    def nova_mao(self):
        """Apaga o histórico da mão anterior."""
        raise NotImplementedError

    def fim_de_partida(self) -> bool:
        raise NotImplementedError
