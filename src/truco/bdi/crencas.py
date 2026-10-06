"""Crenças do jogador (Especificação 4.1; Como os Agentes Decidem 3.3)."""


class Crencas:
    """Fatos (mão, cartas jogadas, placar, rodadas, aposta, conversa) e
    estimativas sobre a mão dos outros três jogadores."""

    def nova_mao(self, cartas):
        """Refaz as crenças estimadas. Mantém o histórico de fuga."""
        raise NotImplementedError

    def registrar_anuncio(self, jogador, categoria, confianca):
        raise NotImplementedError

    def crenca_sobre(self, jogador) -> float:
        raise NotImplementedError
