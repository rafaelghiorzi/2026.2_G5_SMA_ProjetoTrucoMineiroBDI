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
        #      YOUR_TURN        -> await self.act_on_turn(data["can_call"])
        #      ASK_DECLARATION  -> declare()      -> DECLARATION {"category": ... or None}
        #      ASK_RESPONSE     -> answer_call()  -> RESPONSE {"response": fold/accept/raise}
        #      TALK_WINDOW      -> talk()         (the table does not send it yet)
        #      MATCH_END        -> self.kill()
        #    CALL, DECLARATION and RESPONSE are only notices: perceive() is enough.
        raise NotImplementedError

    async def act_on_turn(self, can_call: bool) -> None:
        """Either call truco (only when can_call and should_call()) or play a card.

        No waiting needed: if the call is accepted, the table sends YOUR_TURN
        again (Specification 2.4, rule 8) and this method runs once more.
        """
        raise NotImplementedError


class Player(Agent):

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
