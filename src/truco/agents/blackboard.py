"""Blackboard: runs the talk window of each point.

It keeps the declarations and delivers the signals, without interpreting them. Only
the table opens it, and the players reach it only through messages.
"""

from slixmpp import JID
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour

from truco.communication import create_message, game_template, read_message, sender_of, LoggedSend
from truco.config import Event, Performative, TalkAction
from truco.metrics import MetricsRecorder

import logging
logger = logging.getLogger("truco.board")


class ListenAndRecord(LoggedSend, CyclicBehaviour):
    """Handles the messages of the table and the players, one at a time."""

    agent: "BlackboardAgent"

    async def run(self) -> None:
        msg = await self.receive(timeout=10)
        if msg is None:
            return
        event, data = read_message(msg)
        sender = sender_of(msg)

        match event:
            case Event.DECLARE:
                await self.declare(sender, data)
            case Event.OPEN:
                self.agent.talks[data["point"]] = {
                    "players": [JID(player) for player in data["players"]],
                    "declarations": {},
                    "open": True,
                }
                logger.info(f"Janela de conversa aberta no ponto {data['point']}")
                await self.ack(event, data)
            case Event.CLOSED:
                await self.close_talk(data["point"])
                await self.ack(event, data)

    async def ack(self, event: Event, data: dict) -> None:
        """Confirms an order to the table. After OPEN, only this lets it release the players."""
        await self.send(create_message(
            self.agent.table, Performative.ACCEPT, {"event": event, "point": data.get("point")},
        ))

    # --- Talk window ---

    async def declare(self, player: JID, data: dict) -> None:
        """Each player declares once per point, while the window is open."""
        talk = self.agent.talks.get(data["point"])
        if talk is None or not talk["open"] or player in talk["declarations"]:
            logger.warning(f"Declaração de {player} recusada no ponto {data['point']}: {data.get('action')}")
            await self.send(create_message(player, Performative.REJECT, {"event": Event.DECLARE, **data}))
            return
        talk["declarations"][player] = {"action": TalkAction(data["action"]), "value": data.get("value")}
        value = data.get("value")
        logger.info(f"{player} escolheu {data['action']}" + (f" ({value})" if value else ""))
        await self.send(create_message(player, Performative.ACCEPT, {"event": Event.DECLARE, **data}))

        # Everyone declared before the deadline: deliver the signals and release the table
        if len(talk["declarations"]) == len(talk["players"]):
            await self.close_talk(data["point"])
            await self.send(create_message(
                self.agent.table, Performative.INFORM, {"event": Event.CLOSED, "point": data["point"]},
            ))

    async def close_talk(self, point: int) -> None:
        """Fills whoever is missing with NOTHING and delivers the signals.

        - A partner's SEND always arrives. Whoever did not choose LISTEN trusts it less,
          and the player applies that, not the board.
        - Whoever spied receives everything both opponents sent: SEND and BLUFF.
        - A BLUFF is sent "to nobody": the bluffer's partner does not receive it.

        Closing twice does nothing: the table may ask at the same moment the last player declares.
        """
        talk = self.agent.talks[point]
        if not talk["open"]:
            return
        talk["open"] = False
        players, declarations = talk["players"], talk["declarations"]
        for player in players:
            if player not in declarations:
                logger.warning(f"{player} não declarou a tempo no ponto {point}: conta como {TalkAction.NOTHING}")
            declarations.setdefault(player, {"action": TalkAction.NOTHING, "value": None})
            if self.agent.recorder is not None:
                self.agent.recorder.event(point, None, "talk", player, declarations[player]["action"], None)

        for i, player in enumerate(players):
            partner = players[(i + 2) % 4]
            opponents = [players[(i + 1) % 4], players[(i + 3) % 4]]
            signals = self.signals(declarations, [partner], {TalkAction.SEND})
            if declarations[player]["action"] == TalkAction.SPY:
                signals += self.signals(declarations, opponents, {TalkAction.SEND, TalkAction.BLUFF})
            if signals:
                heard = ", ".join(f"{signal['from']}: {signal['value']}" for signal in signals)
                logger.info(f"{player} recebeu os sinais [{heard}]")
                await self.send(create_message(
                    player, Performative.INFORM,
                    {
                        "event": Event.READING,
                        "point": point,
                        "signals": signals,
                        "my_action": declarations[player]["action"]
                    },
                ))
        logger.info(f"Janela de conversa fechada no ponto {point}")

    def signals(self, declarations: dict, targets: list[JID], actions: set[TalkAction]) -> list[dict]:
        """The signals of the `targets` whose action is in `actions`. Only the value goes out,
        never the action, so whoever receives it cannot tell a bluff from a true SEND."""
        return [
            {"from": target, "value": declarations[target]["value"]}
            for target in targets
            if declarations[target]["action"] in actions
        ]


class BlackboardAgent(Agent):
    """Holds the talk windows, one per point."""

    def __init__(self, jid: JID, password: str, table: JID, recorder: MetricsRecorder | None = None) -> None:
        super().__init__(str(jid), password)
        self.table = table
        self.recorder = recorder
        self.talks: dict[int, dict] = {}  # point -> {"players", "declarations", "open"}

    async def setup(self) -> None:
        self.add_behaviour(ListenAndRecord(), game_template())
