"""Control players, without BDI: fixed rules and no conversation.

They exist to measure whether deliberating makes a difference. They use the same
protocol as everyone (TrucoBehaviour), but replace every decision that uses the recipe.
"""

from slixmpp import JID

from truco.agents.player import TrucoBehaviour
from truco.config import Category, Event, Performative, Response, Source, TalkAction
from truco.game import Card


class ControlBehaviour(TrucoBehaviour):
    """What both control players share: they do not talk and do not declare."""

    async def on_talk_window(self, data: dict) -> None:
        """Does not take part, but says so: otherwise the window would wait for the deadline."""
        await self.tell(
            self.agent.board,
            Performative.REQUEST,
            {
                "event": Event.DECLARE,
                "point": self.agent.point_number,
                "action": TalkAction.NOTHING,
                "value": None,
            },
        )

    def declare(self) -> Category | None:
        return None  # the table treats a null category as "does not take part"

    # Abstract in TrucoBehaviour, so they must exist. Only the recipe calls them,
    # and control players do not use it.

    def bias(self, player: JID) -> float:
        return 0.0

    def trust(self, speaker: JID, category: Category, source: Source) -> float:
        return 0.0

    def call_bonus(self) -> float:
        return 0.0

    def open_round(self) -> Card:
        return self.choose_card()


class Coward(ControlBehaviour):
    """Never calls, always folds, always plays the weakest card."""

    def should_call(self) -> bool:
        return False

    def answer_call(self, value_called: int) -> Response:
        return Response.FOLD

    def choose_card(self) -> Card:
        return self.agent.hand.weakest()


class Madman(ControlBehaviour):
    """Calls whenever it has a manilha, never folds, always plays the strongest card."""

    def should_call(self) -> bool:
        return self.agent.hand.has_manilha

    def answer_call(self, value_called: int) -> Response:
        if value_called >= 12:  # there is nothing above twelve to raise to
            return Response.ACCEPT
        return self.rng.choice([Response.ACCEPT, Response.RAISE])

    def choose_card(self) -> Card:
        return self.agent.hand.strongest()
