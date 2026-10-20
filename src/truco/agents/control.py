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
        raise NotImplementedError  # self.hand.has_manilha and the rules allow it

    def answer_call(self, value_called: int) -> Response:
        raise NotImplementedError  # 50% accept / 50% raise; at 12, accepts

    def choose_card(self) -> Card:
        raise NotImplementedError  # self.hand.strongest()
