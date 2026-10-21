"""Blackboard: guarda tudo o que acontece em cada ponto e conduz a conversa entre jogadores."""

from slixmpp import JID
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour

from truco.communication import create_message, game_template, read_message, sender_of
from truco.config import Event, Performative, TalkAction


class ListenAndRecord(CyclicBehaviour):
    agent: "BlackboardAgent"

    async def run(self) -> None:
        msg = await self.receive(timeout=10)
        if msg is None:
            return
        event, data = read_message(msg)
        sender = sender_of(msg)

        match event:
            case Event.QUERY:
                await self.answer(sender, data)
            case Event.DECLARE:
                await self.declare(sender, data)
            case Event.OPEN:
                self.agent.talks[data["point"]] = {
                    "players": [JID(player) for player in data["players"]],
                    "declarations": {},
                    "open": True,
                }
                await self.ack(event, data)
            case Event.CLOSED:
                await self.close_talk(data["point"])
                await self.ack(event, data)
            case _:
                self.agent.record(event, data)
                await self.ack(event, data)

    async def ack(self, event: Event, data: dict) -> None:
        """Confirma à mesa que gravou: só depois disso ela avisa os jogadores."""
        await self.send(create_message(
            self.agent.table, Performative.ACCEPT, {"event": event, "point": data.get("point")},
        ))

    async def answer(self, asker: JID, data: dict) -> None:
        point = self.agent.points.get(data["point"])
        if point is None:
            await self.send(create_message(asker, Performative.REJECT, {"event": Event.QUERY, **data}))
            return
        await self.send(create_message(
            asker, Performative.INFORM, {"event": Event.QUERY, "point": data["point"], "data": point},
        ))

    # --- Conversa ---

    async def declare(self, player: JID, data: dict) -> None:
        """Cada jogador declara uma vez por ponto, com a janela aberta."""
        talk = self.agent.talks.get(data["point"])
        if talk is None or not talk["open"] or player in talk["declarations"]:
            await self.send(create_message(player, Performative.REJECT, {"event": Event.DECLARE, **data}))
            return
        talk["declarations"][player] = {"action": TalkAction(data["action"]), "value": data.get("value")}
        await self.send(create_message(player, Performative.ACCEPT, {"event": Event.DECLARE, **data}))

        # Todos declararam antes do prazo: resolve e libera a mesa
        if len(talk["declarations"]) == len(talk["players"]):
            await self.close_talk(data["point"])
            await self.send(create_message(
                self.agent.table, Performative.INFORM, {"event": Event.CLOSED, "point": data["point"]},
            ))

    async def close_talk(self, point: int) -> None:
        """Completa quem faltou com NOTHING e entrega os sinais

        - O SEND do parceiro sempre chega: o sinal nunca se perde. Quem não escolheu LISTEN
          ouve com menos confiança (×0,7), e isso é o jogador que aplica.
        - Quem espionou recebe tudo o que os dois adversários mandaram: SEND e BLUFF.
        - O BLUFF é mandado "para ninguém": o parceiro de quem blefou não o recebe.

        Fechar de novo não faz nada: a mesa pode pedir o fechamento junto com a última declaração.
        """
        talk = self.agent.talks[point]
        if not talk["open"]:
            return
        talk["open"] = False
        players, declarations = talk["players"], talk["declarations"]
        for player in players:
            declarations.setdefault(player, {"action": TalkAction.NOTHING, "value": None})

        for i, player in enumerate(players):
            partner = players[(i + 2) % 4]
            opponents = [players[(i + 1) % 4], players[(i + 3) % 4]]
            signals = self.signals(declarations, [partner], {TalkAction.SEND})
            if declarations[player]["action"] == TalkAction.SPY:
                signals += self.signals(declarations, opponents, {TalkAction.SEND, TalkAction.BLUFF})
            if signals:
                await self.send(create_message(
                    player, Performative.INFORM,
                    {"event": Event.READING, "point": point, "signals": signals},
                ))

    def signals(self, declarations: dict, targets: list[JID], actions: set[TalkAction]) -> list[dict]:
        """Os sinais dos `targets` cuja ação está em `actions`. Só o valor sai, nunca a ação:
        quem recebe não distingue um blefe de um envio verdadeiro."""
        return [
            {"from": target, "value": declarations[target]["value"]}
            for target in targets
            if declarations[target]["action"] in actions
        ]


class BlackboardAgent(Agent):
    def __init__(self, jid: JID, password: str, table: JID) -> None:
        super().__init__(str(jid), password)
        self.table = table
        self.points: dict[int, dict[str, list[dict]]] = {}  # ponto -> {evento: [dados, ...]}
        self.talks: dict[int, dict] = {}  # ponto -> {"players", "declarations", "open"}

    def record(self, event: Event, data: dict) -> None:
        point = data.get("point")
        if not isinstance(point, int):
            return
        self.points.setdefault(point, {}).setdefault(event, []).append(data)

    async def setup(self) -> None:
        self.add_behaviour(ListenAndRecord(), game_template())
