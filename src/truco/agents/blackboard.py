import asyncio
from typing import NotRequired, TypedDict

from slixmpp import JID
from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message

from truco.communication import create_message, read_message, game_template, sender_of
from truco.config import (
    TALK_TIMEOUT,
    Category,
    Event,
    TalkAction,
    Performative,
    BoardPhase
)


class BoardState(State):
    """Estado-base do FSM, com referência tipada ao agente Blackboard."""

    agent: "BlackBoardAgent"
    pass

class Inactive(BoardState):
    """Aguarda uma solicitação válida para abrir a conversa de um ponto."""

    class OpenPayload(TypedDict):
            """Dados enviados no payload para abrir a conversa: número do ponto e ordem dos jogadores."""
    
            point: int
            players: list[str]  # JIDs as text, as they travel in the message

    async def run(self) -> None:
        while True:
            msg = await self.receive(timeout=30)
            if msg is None: continue
            if sender_of(msg) != self.agent.table: continue

            got, data = read_message(msg)
            if got != Event.OPEN or msg.get_metadata("performative") != Performative.REQUEST: continue
        
            try:
                self.agent.point = int(data.pop("point"))
                self.agent.players = [JID(player) for player in data.pop("players")]
                await self.send(create_message(self.agent.table, Performative.ACCEPT, {"event": Event.OPEN}))
                self.set_next_state(BoardPhase.OPEN)
                return  # the FSM only changes state when run() returns
            except:
                await self.send(create_message(self.agent.table, Performative.REJECT, {"event": Event.OPEN}))

class Open(BoardState):
    """Coleta as declarações dos jogadores até todos responderem ou expirar o prazo."""

    class Content(TypedDict):   
        action: TalkAction
        value: float | None

    class InputPayload(TypedDict):
        """Declaração enviada por um jogador durante a janela de conversa."""
        point: int
        action: TalkAction
        value: Open.Content # Category.WEAK / MEDIUM / STRONG

    def valid_message(self, msg: Message, expected_players: set[JID], received_players: set[JID]) ->tuple[JID, dict] | None:
        sender = sender_of(msg)
        if sender not in expected_players or sender in received_players:
            return None
        
        if msg.get_metadata("performative") != Performative.REQUEST:
            return None
        try:
            event, body = read_message(msg)
        except (TypeError, ValueError):
            return None
        if event != Event.DECLARE or not isinstance(body, dict):
            return None

        return sender, body 

    
    async def run(self):
        expected_players = set(self.agent.players)
        received_players: set[JID] = set()
        deadline = asyncio.get_running_loop().time() + TALK_TIMEOUT

        while not expected_players.issubset(received_players):
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            msg = await self.receive(timeout=remaining)
            if msg is None:
                continue
            validated = self.valid_message(msg, expected_players, received_players)
            if not validated: 
                continue

            sender, body = validated
            try:
                received_point = int(body["point"])
                action = TalkAction(body["action"])
            except (KeyError, TypeError, ValueError):
                await self.send(create_message(sender, Performative.REJECT, {"event": Event.DECLARE,}))
                continue

            if received_point != self.agent.point:
                await self.send(create_message(sender, Performative.REJECT, {"event": Event.DECLARE,}))
                continue

            self.agent.board.write(
                self.agent.point,
                sender,
                {**body, "action": action.value},
            )
            received_players.add(sender)

        missing_players = expected_players - received_players
        for player in missing_players:
            self.agent.board.write(
                self.agent.point,
                player,
                {"value": None, "action": TalkAction.NOTHING},
            )

        self.set_next_state(BoardPhase.PROCESSING)

class Processing(BoardState):
    """Processa as declarações coletadas e prepara as informações a serem divulgadas."""


    class OutputToPlayerPayload(TypedDict):
        point: int
        action: TalkAction
        value: dict[str, str | Category | None]  # key: player JID as text


    class DeclarationPayload(TypedDict):
        action: TalkAction
        value: dict[str, Category | None]  # key: player JID as text

    def get_teams_info(self, player: JID) -> tuple[JID, tuple[JID, JID]]:
        p = self.agent.players.index(player)
        teammate = self.agent.players[(p+2) % 4]
        opponents = (self.agent.players[(p+1) % 4], self.agent.players[(p+3) % 4])

        return teammate, opponents

    async def run(self):
        for player in self.agent.players:
            teammate, opponents = self.get_teams_info(player)
            declaration = self.agent.board.read(self.agent.point, player)
            if declaration is None:
                continue
            match declaration.get("action"):
                case TalkAction.SPY:
                    first_opponent = self.agent.board.read(self.agent.point, opponents[0])
                    second_opponent = self.agent.board.read(self.agent.point, opponents[1])

                    if first_opponent["action"] == TalkAction.SEND:
                        await self.send(create_message(
                            recipient=player,
                            performative=Performative.INFORM,
                            content={
                                "point": self.agent.point,
                                "value": first_opponent.get("value")
                            }
                        ))
                        continue

                    if second_opponent["action"] == TalkAction.SEND:
                        await self.send(create_message(
                            recipient=player,
                            performative=Performative.INFORM,
                            content={
                                "point": self.agent.point,
                                "value": second_opponent.get("value")
                            }
                        ))
                        continue
                    
                    await self.send(create_message(
                        recipient=player,
                        performative=Performative.INFORM,
                        content={
                            "point": self.agent.point,
                            "value": None
                        }
                    ))
                    continue

                case TalkAction.LISTEN:
                    mate = self.agent.board.read(point=self.agent.point, player=teammate)
                    await self.send(create_message(
                        recipient=player,
                        performative=Performative.INFORM,
                        content={
                            "point": self.agent.point,
                            "value": mate.get("value") if mate["action"] == TalkAction.SEND else None
                        }
                    ))
                    continue

                case TalkAction.BLUFF:
                    # nothing
                    continue
                case TalkAction.SEND:
                    # nothing
                    continue
                case _:
                    # nothing
                    continue

        self.set_next_state(BoardPhase.INACTIVE)
        await self.send(create_message(self.agent.table, Performative.INFORM, {"event": Event.CLOSED}))

class Board:
    """Armazena e recupera dados por ponto e por jogador."""

    def __init__(self) -> None:
        self.data = {}

    def write(
        self,
        point: int,
        player: JID,
        content: dict[str, object],
    ) -> None:
        """Grava ou substitui os dados de um jogador no ponto."""
        self.data.setdefault(point, {})[player] = dict(content)

    def read(self, point: int, player: JID) -> dict[str, object]:
        """Recupera os dados indexados por jogador"""
        point_messages = self.data[point]
        player_message = point_messages[player]
        return player_message


class BlackBoardAgent(Agent):
    """Agente que mantém os dados do Blackboard e executa seu FSM de estados."""

    def __init__(self, jid: JID, password: str, table: JID, players: list[JID], point: int):
        super().__init__(str(jid), password)
        self.table = table
        self.players = players
        self.point = point
        self.board = Board()

    async def setup(self) -> None:
        flow = FSMBehaviour()
        flow.add_state(BoardPhase.INACTIVE, Inactive(), initial=True)
        flow.add_state(BoardPhase.OPEN, Open())
        flow.add_state(BoardPhase.PROCESSING, Processing())

        flow.add_transition(BoardPhase.INACTIVE, BoardPhase.OPEN)
        flow.add_transition(BoardPhase.OPEN, BoardPhase.PROCESSING)
        flow.add_transition(BoardPhase.PROCESSING, BoardPhase.INACTIVE)

        self.add_behaviour(flow)
