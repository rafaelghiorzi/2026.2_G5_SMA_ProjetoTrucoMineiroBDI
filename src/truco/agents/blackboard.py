import asyncio
from typing import TypedDict

from spade.agent import Agent
from spade.message import Message
from spade.behaviour import CyclicBehaviour

from truco.communication import create_message, read_message, game_template
from truco.config import (
    TALK_TIMEOUT,
    Event,
    TalkAction
)


class Board:
    def __init__(self):
        self.board: dict[int, dict] = {}

    def write(self, current_round: int, data: dict, player):
        info = self.board.get(current_round)
        if info is None:
            self.board[current_round] = {player : data}
        else:
            info.update({ player : data })
            self.board.update({ current_round : info})


    def read(self, current_round, player) -> dict | None:
        return self.board.get(current_round)

    def valid_message(self, current_round: int, player: str, data: dict | None) -> TalkAction | None:
        # TODO
        pass
    



class HandleTalkRequests(CyclicBehaviour):
    agent: "BlackBoardAgent"

    async def run(self):
        msg = await self.receive(timeout=TALK_TIMEOUT)
        if msg is None: return # TODO

        player = str(msg.sender.bare)
        event, data = read_message(msg)
        action = data.get("talk_action")
        if action is None: return None # TODO
        if event != Event.TALK_WINDOW: return None # TODO

        match action:
            case TalkAction.SEND:
                await self.publish_message(data, player)
            case TalkAction.BLUFF:
                await self.publish_message(data, player)
            case TalkAction.SPY:
                await self.read_message(player)
            case TalkAction.LISTEN:
                await self.read_message(player)
            case TalkAction.NOTHING:
                return None

            case _: return None

        pass
    async def publish_message(self, data: dict, player: str):
        self.agent.board.write(self.agent.current_round, data, player)

    async def read_message(self, player: str):
        return self.agent.board.read(self.agent.current_round, player)
    
    async def validate_message(self, event: Event, data):
        meta: dict = data.get("metadata")
        # TODO


    
class BlackBoardAgent(Agent):
    def __init__(self, jid: str, password: str, players: list[str]):
        super().__init__(jid, password)
        self.players = players
        self.current_round = 0
        self.board = Board()

    async def setup(self):
        self.add_behaviour(HandleTalkRequests(), game_template())
    



    

