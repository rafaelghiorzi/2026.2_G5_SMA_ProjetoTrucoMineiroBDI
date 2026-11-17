"""Human player: the same protocol as the agents, but every decision comes from a person.

The behaviour answers the same requests as any TrucoBehaviour. Instead of running the
recipe, it publishes a prompt (what is being asked and the options) and waits until
the web server hands back the person's choice through answer(). The beliefs keep being
updated by TrucoBehaviour, so for the table and the board this seat is just one more
player talking FIPA-ACL.

    Player(jid, password, team, table, board, partner, opponents, Human(hub.publish))
"""

import asyncio
from collections.abc import Awaitable, Callable

from slixmpp import JID

from truco.agents.player import TrucoBehaviour
from truco.config import BET_LEVELS, HUMAN_SPY_SUCCESS, Category, Rank, Response, Source, TalkAction
from truco.game import Card


class Human(TrucoBehaviour):
    """Asks the person for every decision. Declarations stay automatic: they are always true."""

    def __init__(self, publish: Callable[[dict], Awaitable[None]]) -> None:
        super().__init__(think_time=None)  # the person is the thinking time
        self.publish = publish
        self.prompt: dict | None = None  # what the person is being asked right now
        self.pending: asyncio.Future[dict] | None = None

    # --- Talking to the person ---

    async def ask(self, kind: str, **options) -> dict:
        """Publishes the prompt and waits for answer() to deliver the choice."""
        self.prompt = {"kind": kind, **options}
        self.pending = asyncio.get_running_loop().create_future()
        await self.publish({"event": "prompt", "player": str(self.agent.me), "point": self.agent.point_number, **self.prompt})
        try:
            return await self.pending
        finally:
            self.prompt = self.pending = None
            await self.publish({"event": "prompt-done", "player": str(self.agent.me), "kind": kind})

    def answer(self, choice: dict) -> str | None:
        """Called by the web server. Returns why the choice was refused, or None if it was taken."""
        if self.prompt is None or self.pending is None or self.pending.done():
            return "Nenhuma decisão pendente."
        if choice.get("kind") != self.prompt["kind"]:
            return f"A decisão pendente é '{self.prompt['kind']}'."
        error = self.invalid(choice)
        if error is None:
            self.pending.set_result(choice)
        return error

    def invalid(self, choice: dict) -> str | None:
        """The same checks the table and the board make, so a bad click never costs a retry."""
        prompt = self.prompt
        assert prompt is not None
        match prompt["kind"]:
            case "turn":
                if choice.get("call"):
                    return None if prompt["can_call"] else "Não é possível pedir truco agora."
                if choice.get("card") not in prompt["hand"]:
                    return "Essa carta não está na sua mão."
            case "response":
                if choice.get("response") not in list(Response):
                    return "Resposta inválida."
                if choice["response"] == Response.RAISE and not prompt["can_raise"]:
                    return "Não há como aumentar mais."
            case "talk":
                if choice.get("action") not in list(TalkAction):
                    return "Ação de conversa inválida."
                if choice["action"] == TalkAction.BLUFF and choice.get("value") not in prompt["bluffs"]:
                    return "O blefe precisa anunciar uma categoria diferente da sua mão."
        return None

    # --- Requests: the person decides ---

    async def on_your_turn(self, data: dict) -> None:
        choice = await self.ask("turn", can_call=data["can_call"], hand=[card.rank for card in self.agent.hand])
        if choice.get("call"):
            await self.call_truco()
            return
        await self.play_card(Card(Rank(choice["card"])))

    async def on_ask_response(self, data: dict) -> None:
        value = data["value"]
        choice = await self.ask("response", value=value, can_raise=value < BET_LEVELS[-1])
        await self.respond(Response(choice["response"]), value)

    async def on_talk_window(self, data: dict) -> None:
        """Same rules as the agents: SEND tells the truth, BLUFF anything else, SPY may fail."""
        real = self.agent.hand.category
        choice = await self.ask("talk", category=real, bluffs=[c for c in Category if c != real])
        action, value = TalkAction(choice["action"]), None
        spy_failed = False
        match action:
            case TalkAction.SPY:
                if self.rng.random() >= HUMAN_SPY_SUCCESS:
                    action, spy_failed = TalkAction.NOTHING, True
            case TalkAction.SEND:
                value = real
            case TalkAction.BLUFF:
                value = Category(choice["value"])
            case _:
                pass
        await self.publish({
            "event": "human-talk", "player": str(self.agent.me), "point": self.agent.point_number,
            "action": choice["action"], "value": value, "spy_failed": spy_failed,
        })
        await self.declare_talk(action, value)

    # --- Notices: only what this seat heard, shown to the person ---

    async def on_reading(self, data: dict) -> None:
        await super().on_reading(data)
        if data["point"] == self.agent.point_number:
            await self.publish({"event": "human-reading", "player": str(self.agent.me), **data})

    # The recipe is never used: the person decides. Abstract in TrucoBehaviour, so they must exist.

    def bias(self, player: JID) -> float:
        return 0.0

    def trust(self, speaker: JID, category: Category, source: Source) -> float:
        return 0.0

    def call_bonus(self) -> float:
        return 0.0

    def open_round(self) -> Card:
        return self.agent.hand.weakest()

    def snapshot(self) -> dict:
        return {}
