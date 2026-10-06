"""Jogador deliberativo: roda o ciclo BDI (perceber, deliberar, agir).
Reconsideração por evento (Especificação 4.3)."""

from truco.agents.jogadores.jogador_agent import JogadorAgent


class JogadorBDI(JogadorAgent):
    def perceber(self, mensagem):
        raise NotImplementedError

    def deliberar(self):
        raise NotImplementedError

    def declarar(self):
        raise NotImplementedError

    def conversar(self):
        raise NotImplementedError
