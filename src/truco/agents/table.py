"""Table: referee and environment (Specification, Section 3). Reactive, state machine.

The rules live in truco.game; the table only keeps the board, talks to the
players and calls the rules at the right time.
"""

import asyncio
import random


from slixmpp import JID
from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State
from spade.message import Message

from truco.agents.blackboard import BlackboardAgent
from truco.communication import create_message, game_template, read_message, sender_of, LoggedSend
from truco.config import (
    POINTS_TO_WIN,
    TEAM,
    TEAMS,
    TURN_TIMEOUT,
    TALK_TIMEOUT,
    MAX_RETRIES,
    Category,
    Event,
    Performative,
    Rank,
    Response,
    TablePhase,
)
from truco.game import Bet, Card, CardsOnTable, Deck, Hand, Point

import logging
logger = logging.getLogger("truco.table")

class TableState(LoggedSend, State):
    """Base of the states: only gives the editor the right type for self.agent."""
    agent: "TableAgent"

    async def notify_all(self, content: dict) -> None:
        """Sends the same notice to the 4 players."""
        for player in self.agent.players:
            await self.send(create_message(player, Performative.INFORM, content))

    async def announce_call(self, caller: JID, value: int) -> None:
        """Public notice of a call (or raise): everyone hears it, and it says who must answer."""
        table = self.agent
        table.answering = table.bet.responder(caller)
        await self.notify_all({
            "event": Event.CALL,
            "player": caller,
            "value": value,
            "responder": table.answering,
        })

    async def wait_from(self, player: JID, timeout: float = TURN_TIMEOUT) -> Message | None:
        """
        The next message from `player`. Messages from anyone else are discarded
        """
        deadline = asyncio.get_running_loop().time() + timeout
        while (remaining := deadline - asyncio.get_running_loop().time()) > 0:
            msg = await self.receive(timeout=remaining)
            if msg is None:
                return None
            if sender_of(msg) == player:
                return msg
            logger.debug(f"Discarded {msg.get_metadata("event")} from {sender_of(msg)}, waiting for {player}")
        return None

    async def wait_for(self, player: JID, event: Event, timeout: float = TURN_TIMEOUT) -> dict | None:
        """
        Waits up to `timeout` for `event` from `player` and returns its data. None = it did not come.
        """
        deadline = asyncio.get_running_loop().time() + timeout
        while (remaining := deadline - asyncio.get_running_loop().time()) > 0:
            msg = await self.wait_from(player, remaining)
            if msg is None:
                return None
            got, data = read_message(msg)
            if got == event:
                return data
        return None


class StartPoint(TableState):
    """Starts a point: new cards, bet worth 1, and each player receives their hand."""

    async def run(self) -> None:
        table = self.agent 

        # 1. New deck for every point: the 29 cards come back and are shuffled.
        deck = Deck(table.rng)
        deck.shuffle()
        table.hands = deck.deal(table.players)

        # 2. New Point and Bet: no round played, point worth 1.
        table.point_number += 1
        table.point = Point(table.players)
        table.bet = Bet(table.players)
        table.cards_on_table = []
        table.fold_result = None

        # 3. Each player receives ONLY their own cards.
        for player, hand in table.hands.items():
            content = {
                "event": Event.NEW_POINT,
                "point": table.point_number,
                "cards": [card.rank for card in hand],  # a Card isn't JSON; its rank is
                "opener": table.opener,
                "score": table.score,
            }
            await self.send(create_message(player, Performative.INFORM, content))

        logger.info(f"Inicio do ponto {table.point_number}. Cartas distribuidas")

        # 4. Who opens the 1st round of this point. From here on, the Turn state takes over.
        table.turn = table.opener
        self.set_next_state(TablePhase.PLAYER_TALK)


class PlayerTalk(TableState):
    """
    The talk window of the point: one per point, after the deal and before the first card.
    Whatever happens in it, the game moves on to TURN
    """

    async def run(self) -> None:
        table = self.agent
        self.set_next_state(TablePhase.TURN)

        # 1. Open the board. If it does not answer, this point simply has no conversation.
        await self.send(create_message(
            table.board, Performative.REQUEST,
            {"event": Event.OPEN, "point": table.point_number, "players": table.players},
        ))
        if await self.wait_for(table.board, Event.OPEN) is None:
            logger.error("board did not open point %d; skipping the talk", table.point_number)
            return

        # 2. Only now the four players are released to talk through the board.
        await self.notify_all({"event": Event.TALK_WINDOW, "point": table.point_number})

        # 3. Normal case: everyone declared and the board warns us before the deadline.
        if await self.wait_for(table.board, Event.CLOSED, TALK_TIMEOUT) is not None:
            return

        # 4. Deadline: the board fills the missing players with NOTHING and delivers the signals.
        logger.warning("talk deadline in point %d; asking the board to close", table.point_number)
        await self.send(create_message(
            table.board, Performative.REQUEST, {"event": Event.CLOSED, "point": table.point_number},
        ))
        if await self.wait_for(table.board, Event.CLOSED) is None:
            logger.error("board did not close point %d; moving on anyway", table.point_number)


class Turn(TableState):
    """Asks whoever has the turn to play and waits for the card or a truco call.

    Each run handles ONE message. If nothing valid arrives, the state points
    to itself (TURN -> TURN) and asks the same player again.
    """

    async def run(self) -> None:
        table = self.agent
        can_call = table.bet.can_call(table.turn, table.point.current_round)

        # 1. Ask whoever has the turn to play, telling them whether they may call.
        await self.send(create_message(
            table.turn, Performative.REQUEST, {"event": Event.YOUR_TURN, "can_call": can_call},
        ))

        # 2. Wait for the answer. No answer in time: ask again.
        msg = await self.wait_from(table.turn)

        # 3. A truco call (Specification 2.4, rules 1 and 2): announce it and go to the declarations.
        if msg is not None and can_call and read_message(msg)[0] == Event.CALL:
            table.strikes = 0
            value = table.bet.call(table.turn)
            await self.announce_call(table.turn, value)
            logger.info(f"O jogador {table.turn} pediu truco!")
            self.set_next_state(TablePhase.DECLARE)
            return

        # 4. Otherwise it must be a card. Missing or invalid: try again, then force it.
        card = None if msg is None else self.valid_card(msg)
        if card is None:
            table.strikes += 1
            logger.warning("no valid play from %s (%d/%d)", table.turn, table.strikes, MAX_RETRIES)
            if table.strikes < MAX_RETRIES:
                self.set_next_state(TablePhase.TURN)
                return
            card = table.hands[table.turn].weakest()
            logger.error("%s did not answer; the table plays %s", table.turn, card.rank)
        table.strikes = 0

        # 5. Apply it to the board and notify the 4 (including the player: it is the confirmation).
        table.hands[table.turn].remove(card)
        table.cards_on_table.append((table.turn, card))
        await self.notify_all({
            "event": Event.CARD_PLAYED,
            "player": table.turn,
            "card": card.rank,
        })
        logger.info(f"Jogador {table.turn} jogou a carta {card.rank}")

        # 6. A full round goes to END_ROUND; otherwise the turn moves on.
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
        if sender_of(msg) != table.turn:
            return None
        try:
            card = Card(Rank(data.get("card")))
        except ValueError:  # not a card rank that exists
            return None
        if card not in table.hands[table.turn]:
            return None
        return card


class Declare(TableState):
    """Before answering, the answering pair declares in public (Specification 2.4 rule 4, 6.3).

    First the responder's partner, then the responder. A player who does not take part
    (control players) answers with a null category, and whoever does not answer in time
    is skipped: a declaration never blocks the game.
    """

    async def run(self) -> None:
        table = self.agent

        for declarer in (table.partner_of(table.answering), table.answering):
            await self.send(create_message(
                declarer, Performative.REQUEST, {"event": Event.ASK_DECLARATION},
            ))
            data = await self.wait_for(declarer, Event.DECLARATION)
            if data is None:
                logger.warning(f"{declarer} did not declare in time, skipping")
                continue
            try:
                category = Category(data.get("category"))
            except ValueError:  # null (does not take part) or an unknown category
                continue
            await self.notify_all({
                "event": Event.DECLARATION,
                "player": declarer,
                "category": category,
            })
            logger.info(f"Jogador {declarer} declarou sua mão {category}")

        self.set_next_state(TablePhase.AWAIT_ANSWER)


class AwaitAnswer(TableState):
    """Asks the responder to fold, accept or raise (Specification 2.4, rules 3 to 8)."""

    async def run(self) -> None:
        table = self.agent
        bet = table.bet

        # 1. Ask the responder. No valid answer in time: ask again (without redoing the declarations).
        await self.send(create_message(
            table.answering, Performative.PROPOSE, {"event": Event.ASK_RESPONSE, "value": bet.pending},
        ))
        data = await self.wait_for(table.answering, Event.RESPONSE)
        response = self.valid_response(data)
        if response is None:
            table.strikes += 1
            logger.warning(f"Sem resposta válida de {table.answering} ({table.strikes}/{MAX_RETRIES})")
            if table.strikes < MAX_RETRIES:
                self.set_next_state(TablePhase.AWAIT_ANSWER)
                return
            response = Response.FOLD # Whoever never answers runs away
            logger.error(f"{table.answering} Não responder. Contando como fuga.")
            print(f"[table] no valid answer from {table.answering}, asking again")
        table.strikes = 0

        # 2. Everyone hears the answer.
        responder = table.answering
        await self.notify_all({
            "event": Event.RESPONSE,
            "player": responder,
            "response": response,
            "value": bet.pending,
        })

        # 3. Fold ends the point; accept gives the turn back to whoever had it (rule 8);
        #    raise = accept + call the next level: a new call, with its own declarations.
        if response == Response.FOLD:
            table.fold_result = bet.fold()
            logger.info(f"Jogador {responder} decidiu fugir!")
            self.set_next_state(TablePhase.END_POINT)
        elif response == Response.ACCEPT:
            bet.accept()
            logger.info(f"Jogador {responder} aceitou o truco!")
            self.set_next_state(TablePhase.TURN)
        else:
            new_value = bet.raise_bet(responder)
            logger.info(f"Jogador {responder} quer aumentar a aposta!")
            await self.announce_call(responder, new_value)
            self.set_next_state(TablePhase.DECLARE)

    def valid_response(self, data: dict | None) -> Response | None:
        """The answer, if it is one the rules allow. Raising past twelve is not."""
        table = self.agent
        if data is None:
            return None
        try:
            response = Response(data.get("response"))
        except ValueError:
            return None
        if response == Response.RAISE and not table.bet.can_call(table.answering, table.point.current_round):
            return None
        return response


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

        logger.info(f"Fim da rodada, a equipe {winner} venceu.")

        # 3. End the point
        if table.point.finished:
            self.set_next_state(TablePhase.END_POINT)
        else:
            logger.info(f"Iniciando próxima rodada")
            table.turn = table.point.who_starts(table.cards_on_table)
            table.cards_on_table = []
            self.set_next_state(TablePhase.TURN)


class EndPoint(TableState):
    async def run(self) -> None:
        table = self.agent

        # A point ends by the rounds or by someone folding (then Bet.fold decided it).
        if table.fold_result is not None:
            winner, points = table.fold_result
        else:
            winner, points = table.point.point_winner(), table.bet.value
        if winner is not None:
            table.score[winner] += points

        await self.notify_all({
            "event" : Event.POINT_END,
            "winner": winner,
            "points": points,
            "score": table.score
        })

        logger.info(f"Fim do ponto, a equipe {winner} ganhou mais {points} ponto(s).")
        logger.info("Placar atual:")
        for time, pontos in table.score.items():
            logger.info(f"  Time {time}: {pontos} ponto(s).")


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

        logger.info(f"A partida acabou! Placar final:")
        for time, pontos in table.score.items():
            logger.info(f"  Time {time}: {pontos} ponto(s).")

        await table.stop()


class TableAgent(Agent):
    def __init__(self, jid: JID, password: str, board: JID, players: list[JID], seed: int | None = None):
        super().__init__(str(jid), password)
        # Information board: everything the table knows lives here, and the states read/write it
        self.board = board
        self.players = players  # seat order: A, B, A, B
        self.rng = random.Random(seed)
        self.score: dict[TEAM, int] = {team: 0 for team in TEAMS}
        self.opener = players[0]  # P1 opens the first point
        self.point_number = 0  # points played so far; identifies the point in messages
        self.turn = self.opener
        self.hands: dict[JID, Hand] = {}
        self.cards_on_table: CardsOnTable = []
        self.point = Point(players)
        self.bet = Bet(players)
        self.answering = self.opener  # who must answer the current call
        self.fold_result: tuple[TEAM, int] | None = None  # set when a point ends by folding
        self.strikes = 0

    def next_seat(self, player: JID) -> JID:
        """Next seat in play order."""
        i = self.players.index(player)
        return self.players[(i + 1) % len(self.players)]

    def partner_of(self, player: JID) -> JID:
        """Partners sit two seats apart."""
        i = self.players.index(player)
        return self.players[(i + 2) % len(self.players)]

    async def setup(self) -> None:
        flow = FSMBehaviour()
        # States
        flow.add_state(TablePhase.START_POINT, StartPoint(), initial=True)
        flow.add_state(TablePhase.PLAYER_TALK, PlayerTalk())
        flow.add_state(TablePhase.TURN, Turn())
        flow.add_state(TablePhase.DECLARE, Declare())
        flow.add_state(TablePhase.AWAIT_ANSWER, AwaitAnswer())
        flow.add_state(TablePhase.END_ROUND, EndRound())
        flow.add_state(TablePhase.END_POINT, EndPoint())
        flow.add_state(TablePhase.END_MATCH, EndMatch())

        # Possible transitions between states
        flow.add_transition(TablePhase.START_POINT, TablePhase.PLAYER_TALK)
        flow.add_transition(TablePhase.PLAYER_TALK, TablePhase.TURN)
        flow.add_transition(TablePhase.TURN, TablePhase.TURN)
        flow.add_transition(TablePhase.TURN, TablePhase.END_ROUND)
        flow.add_transition(TablePhase.TURN, TablePhase.DECLARE)
        flow.add_transition(TablePhase.DECLARE, TablePhase.AWAIT_ANSWER)
        flow.add_transition(TablePhase.AWAIT_ANSWER, TablePhase.AWAIT_ANSWER)
        flow.add_transition(TablePhase.AWAIT_ANSWER, TablePhase.TURN)
        flow.add_transition(TablePhase.AWAIT_ANSWER, TablePhase.DECLARE)
        flow.add_transition(TablePhase.AWAIT_ANSWER, TablePhase.END_POINT)
        flow.add_transition(TablePhase.END_ROUND, TablePhase.TURN)
        flow.add_transition(TablePhase.END_ROUND, TablePhase.END_POINT)
        flow.add_transition(TablePhase.END_POINT, TablePhase.START_POINT)
        flow.add_transition(TablePhase.END_POINT, TablePhase.END_MATCH)

        self.add_behaviour(flow, game_template())
