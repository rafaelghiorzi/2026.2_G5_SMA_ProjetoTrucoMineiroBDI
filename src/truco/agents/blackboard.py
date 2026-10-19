import asyncio
from typing import NotRequired, TypedDict

from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message

from truco.communication import create_message, read_message, game_template
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
    """Aguarda uma solicitação válida para abrir uma rodada."""

    class OpenPayload(TypedDict):
            """Dados enviados no payload para abrir uma rodada: número e ordem dos jogadores."""
    
            round: int
            players: list[str]

    async def run(self) -> None:
        while True:
            msg = await self.receive()
            if msg is None: continue
            sender = str(msg.sender)
            if sender != self.agent.table: continue

            got, data = read_message(msg)
            if got != Event.OPEN or msg.get_metadata("performative") != Performative.REQUEST: continue
        
            try:
                self.agent.round = int(data.pop("round"))
                self.agent.players = data.pop("players")
                await self.send(create_message(self.agent.table, Performative.ACCEPT, {"event": Event.OPEN}))
                self.set_next_state(BoardPhase.OPEN)
            except:
                await self.send(create_message(self.agent.table, Performative.REJECT, {"event": Event.OPEN}))


class Open(BoardState):
    """Coleta as declarações dos jogadores até todos responderem ou expirar o prazo."""

    class Content(TypedDict):
        action: TalkAction
        value: float | None

    class InputPayload(TypedDict):
        """Declaração enviada por um jogador durante a janela de conversa."""
        round: int
        action: TalkAction
        value: Open.Content # Category.WEAK / MEDIUM / STRONG

    def valid_message(self, msg: Message, expected_players: set, received_players: set) ->tuple[str, dict] | None:
        sender = str(msg.sender.bare)
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
        received_players = set()
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
                received_round = int(body["round"])
                action = TalkAction(body["action"])
            except (KeyError, TypeError, ValueError):
                await self.send(create_message(sender, Performative.REJECT, {"event": Event.DECLARE,}))
                continue

            if received_round != self.agent.round:
                await self.send(create_message(sender, Performative.REJECT, {"event": Event.DECLARE,}))
                continue

            self.agent.board.write(
                self.agent.round,
                sender,
                {**body, "action": action.value},
            )
            received_players.add(sender)

        missing_players = expected_players - received_players
        for player in missing_players:
            self.agent.board.write(
                self.agent.round,
                player,
                {"value": None, "action": TalkAction.NOTHING},
            )

        self.set_next_state(BoardPhase.PROCESSING)


class Processing(BoardState):
    """Processa as declarações coletadas e prepara as informações a serem divulgadas."""


    class OutputToPlayerPayload(TypedDict):
        round: int
        action: TalkAction
        value: dict[str, str | Category | None]


    class DeclarationPayload(TypedDict):
        action: TalkAction
        value: dict[str, Category | None]

    def get_teams_info(self, player: str) -> tuple[str, tuple[str, str]]:
        p = self.agent.players.index(player)
        teammate = self.agent.players[(p+2) % 4]
        opponents = (self.agent.players[(p+1) % 4], self.agent.players[(p+3) % 4])

        return teammate, opponents

    async def run(self):
        for player in self.agent.players:
            teammate, opponents = self.get_teams_info(player)
            declaration = self.agent.board.read(self.agent.round, player)
            if declaration is None:
                continue
            match declaration.get("action"):
                case TalkAction.SPY:
                    first_opponent = self.agent.board.read(self.agent.round, opponents[0])
                    second_opponent = self.agent.board.read(self.agent.round, opponents[1])
                    continue
                case TalkAction.LISTEN:
                    #TODO read_teammate
                    continue
                case TalkAction.BLUFF:
                    #TODO nothing
                    continue
                case TalkAction.SEND:
                    #TODO nothing
                    continue

                case _:
                    # TODO nothing
                    continue

        self.set_next_state(BoardPhase.INACTIVE)
        await self.send(create_message(self.agent.table, Performative.INFORM, {"event": Event.CLOSED}))
        pass


class Board:
    """Armazena e recupera dados por rodada e por jogador."""

    def __init__(self) -> None:
        self.data = {}

    def write(
        self,
        round: int,
        player: str,
        content: dict[str, object],
    ) -> None:
        """Grava ou substitui os dados de um jogador na rodada."""
        self.data.setdefault(round, {})[player] = dict(content)

    def read(self, round: int, player: str) -> dict[str, object]:
        """Recupera os dados indexados por jogador; retorna None se algum não existir."""
        round_messages = self.data[round]
        player_message = round_messages[player]
        return player_message


class BlackBoardAgent(Agent):
    """Agente que mantém os dados do Blackboard e executa seu FSM de estados."""

    def __init__(self, jid: str, password: str, table: str, players: list[str], round: int):
        super().__init__(jid, password)
        self.table = table
        self.players = players
        self.round = round
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
