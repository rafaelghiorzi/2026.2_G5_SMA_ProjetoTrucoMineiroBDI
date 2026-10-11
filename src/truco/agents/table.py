"""Table: referee and environment (Specification, Section 3). Reactive, state machine.

The rules live in truco.game; the table only keeps the board, talks to the
players and calls the rules at the right time.
"""

import random

from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message

from truco.communication import create_message, game_template, read_message
from truco.config import (
    POINTS_TO_WIN,
    TEAM,
    TEAMS,
    TURN_TIMEOUT,
    Event,
    Performative,
    Rank,
    TablePhase,
)
from truco.game import Bet, Card, CardsOnTable, Deck, Hand, Point


class TableState(State):
    """Base of the states: only gives the editor the right type for self.agent."""
    agent: "TableAgent"

    async def notify_all(self, content: dict) -> None:
        """Sends the same notice to the 4 players."""
        for player in self.agent.players:
            await self.send(create_message(player, Performative.INFORM, content))


class StartPoint(TableState):
    """Starts a point: new cards, bet worth 1, and each player receives their hand."""

    async def run(self) -> None:
        table = self.agent  # the board: everything the states read and write lives on the agent

        # 1. New deck for every point: the 29 cards come back and are shuffled.
        deck = Deck(table.rng)
        deck.shuffle()
        table.hands = deck.deal(table.players)

        # 2. New Point and Bet: no round played, point worth 1.
        table.point = Point(table.players)
        table.bet = Bet(table.players)
        table.cards_on_table = []

        # 3. Each player receives ONLY their own cards. This is what guarantees the
        #    partial view (Specification 3): the others' hands never reach them.
        for player, hand in table.hands.items():
            content = {
                "event": Event.NEW_POINT,
                "cards": [card.rank for card in hand],  # a Card isn't JSON; its rank is
                "opener": table.opener,
                "score": table.score,
            }
            await self.send(create_message(player, Performative.INFORM, content))

        # 4. Who opens the 1st round of this point. From here on, the Turn state takes over.
        table.turn = table.opener
        self.set_next_state(TablePhase.TURN)


class Turn(TableState):
    """Asks whoever has the turn to play and waits for the card.

    Each run handles ONE card. If nothing valid arrives, the state points
    to itself (TURN -> TURN) and asks the same player again.
    Step 4 (truco): a PROPOSE may also arrive here instead of a card.
    """

    async def run(self) -> None:
        table = self.agent

        # 1. Ask whoever has the turn to play.
        await self.send(create_message(table.turn, Performative.REQUEST, {"event": Event.YOUR_TURN}))

        # 2. Wait for the answer. No answer in time: ask again.
        msg = await self.receive(timeout=TURN_TIMEOUT)
        if msg is None:
            print(f"[table] {table.turn} did not play in time, asking again")
            self.set_next_state(TablePhase.TURN)
            return

        # 3. Validate. An invalid play is ignored and the turn stays with the same player.
        card = self.valid_card(msg)
        if card is None:
            print(f"[table] invalid play from {msg.sender.bare}: {msg.body}")
            self.set_next_state(TablePhase.TURN)
            return

        # 4. Apply it to the board and notify the 4 (including the player: it is the confirmation).
        table.hands[table.turn].remove(card)
        table.cards_on_table.append((table.turn, card))
        await self.notify_all({
            "event": Event.CARD_PLAYED,
            "player": table.turn,
            "card": card.rank,
        })

        # 5. A full round goes to END_ROUND; otherwise the turn moves on.
        if len(table.cards_on_table) == len(table.players):
            self.set_next_state(TablePhase.END_ROUND)
        else:
            table.turn = table.next_seat(table.turn)
            self.set_next_state(TablePhase.TURN)

    def valid_card(self, msg: Message) -> Card | None:
        """The card played, if the play is valid (Specification 3, item 2). Otherwise, None."""
        table = self.agent
        event, data = read_message(msg)
        if event != Event.CARD_PLAYED:
            return None
        if str(msg.sender.bare) != table.turn:  # bare: without the connection suffix (/resource)
            return None
        try:
            card = Card(Rank(data.get("card")))
        except ValueError:  # not a card rank that exists
            return None
        if card not in table.hands[table.turn]:
            return None
        return card


class EndRound(TableState):
    async def run(self) -> None:
        table = self.agent

        # 1. Record the round
        winner = table.point.record_round(table.cards_on_table)

        # 2. Notify all players
        await self.notify_all({
            "event": Event.ROUND_END,
            "winner": winner
            })

        # 3. End the point
        if table.point.finished:
            self.set_next_state(TablePhase.END_POINT)
        else:
            table.turn = table.point.who_starts(table.cards_on_table)
            table.cards_on_table = []
            self.set_next_state(TablePhase.TURN)


class EndPoint(TableState):
    async def run(self) -> None:
        table = self.agent

        winner = table.point.point_winner()
        if winner is not None:
            table.score[winner] += table.bet.value

        await self.notify_all({
            "event" : Event.POINT_END,
            "winner": winner,
            "score": table.score
        })

        for points in table.score.values():
            if points >= POINTS_TO_WIN:
                self.set_next_state(TablePhase.END_MATCH)
                break
        else:
            table.opener = table.next_seat(table.opener)
            self.set_next_state(TablePhase.START_POINT)


class EndMatch(TableState):
    """Final state: no outgoing transition, the FSM stops here."""

    async def run(self) -> None:
        table = self.agent

        await self.notify_all({
            "event" : Event.MATCH_END,
            "score" : table.score

        })

        await table.stop()


class TableAgent(Agent):
    def __init__(self, jid: str, password: str, players: list[str], seed: int | None = None):
        super().__init__(jid, password)
        # Information board: everything the table knows lives here, and the states read/write it
        self.players = players  # seat order: A, B, A, B
        self.rng = random.Random(seed)
        self.score: dict[TEAM, int] = {team: 0 for team in TEAMS}
        self.opener = players[0]  # P1 opens the first point
        self.turn = self.opener
        self.hands: dict[str, Hand] = {}
        self.cards_on_table: CardsOnTable = []
        self.point = Point(players)
        self.bet = Bet(players)

    def next_seat(self, player: str) -> str:
        """Next seat in play order."""
        i = self.players.index(player)
        return self.players[(i + 1) % len(self.players)]

    async def setup(self) -> None:
        flow = FSMBehaviour()
        flow.add_state(TablePhase.START_POINT, StartPoint(), initial=True)
        flow.add_state(TablePhase.TURN, Turn())
        flow.add_state(TablePhase.END_ROUND, EndRound())
        flow.add_state(TablePhase.END_POINT, EndPoint())
        flow.add_state(TablePhase.END_MATCH, EndMatch())

        flow.add_transition(TablePhase.START_POINT, TablePhase.TURN)
        flow.add_transition(TablePhase.TURN, TablePhase.TURN)
        flow.add_transition(TablePhase.TURN, TablePhase.END_ROUND)
        flow.add_transition(TablePhase.END_ROUND, TablePhase.TURN)
        flow.add_transition(TablePhase.END_ROUND, TablePhase.END_POINT)
        flow.add_transition(TablePhase.END_POINT, TablePhase.START_POINT)
        flow.add_transition(TablePhase.END_POINT, TablePhase.END_MATCH)

        self.add_behaviour(flow, game_template())
