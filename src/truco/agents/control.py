"""Control players, without BDI (Specification 5.1).

They only inherit the Player protocol; no beliefs and no talking.
"""

from truco.agents.player import Player
from truco.config import Response
from truco.game import Card


class Coward(Player):
    def should_call(self) -> bool:
        return False

    def answer_call(self, value_called: int) -> Response:
        return Response.FOLD

    def choose_card(self) -> Card:
        return self.hand.weakest()


class Madman(Player):
    def should_call(self) -> bool:
        return self.hand.has_manilha

    def answer_call(self, value_called: int) -> Response:
        if value_called > 12:
            return Response.ACCEPT
        return self.rng.choice([Response.ACCEPT, Response.RAISE])

    def choose_card(self) -> Card:
        return self.hand.strongest()
