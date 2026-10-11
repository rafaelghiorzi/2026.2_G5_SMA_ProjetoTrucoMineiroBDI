"""Base behaviour of ALL players (BDI and control).

Only the protocol with the table lives here: receive notices, perceive, and when
the table asks for an action, ask the subclass what to do and answer. The
decisions themselves are abstract: BDIPlayer implements them with the
personality's recipe, Coward and Madman with fixed rules.
"""

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour

from truco.config import Category, Event, Response, TalkAction
from truco.game import Card, Hand


class ListenToTable(CyclicBehaviour):
    """Loop perceive -> (if it is my turn to act) decide -> act.

    Implements "reconsideration on events" (Specification 4.3): the agent only
    deliberates when a message that asks for an action arrives.
    """

    agent: "Player"

    async def run(self) -> None:
        # TODO:
        # 1. msg = await self.receive(timeout=...)
        # 2. event, data = read_message(msg)
        # 3. self.agent.perceive(event, data)   (every notice updates the state)
        # 4. if the event asks for an action, dispatch to the right method:
        #      YOUR_TURN        -> await self.act_on_turn()
        #      CALL (to me)     -> answer_call
        #      ASK_DECLARATION  -> declare
        #      TALK_WINDOW      -> talk
        #      MATCH_END        -> self.kill()
        raise NotImplementedError

    async def act_on_turn(self) -> None:
        """Call before playing (if it wants to) and then play the card.

        If it calls, the play only happens after the table announces the call
        was accepted (Specification 2.4, rule 8) — so this method may need to
        wait for the answer or be split into two events.
        """
        raise NotImplementedError


class Player(Agent):
    """Shared base. Knows who the table, the partner and the opponents are."""

    def __init__(self, jid: str, password: str, table: str, partner: str, opponents: list[str]):
        super().__init__(jid, password)
        self.table = table
        self.partner = partner
        self.opponents = opponents
        self.hand = Hand()

    async def setup(self) -> None:
        # TODO: add_behaviour(ListenToTable(), game_template()).
        # Talk between partners does not go through the table: decide whether it
        # becomes another behaviour or goes into the same dispatch.
        raise NotImplementedError

    # --- Perception. Default: only keeps its own hand. BDI overrides. ---

    def perceive(self, event: Event, data) -> None:
        raise NotImplementedError

    # --- Decisions (Specification 4.4). Each kind of player implements them. ---

    def should_call(self) -> bool:
        raise NotImplementedError

    def answer_call(self, value_called: int) -> Response:
        raise NotImplementedError

    def choose_card(self) -> Card:
        raise NotImplementedError

    def declare(self) -> Category | None:
        """None = does not take part (control players)."""
        return None

    def talk(self) -> TalkAction:
        return TalkAction.NOTHING
