"""HTTP/WebSocket bridge between the spectator agent and the browser.

Entry point of the spectator: embedded XMPP server + agents + web server in one event loop.
"""

import asyncio
import random
import socket
import sys
from contextlib import asynccontextmanager, suppress
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import spade
import uvicorn
from slixmpp import JID

from truco.agents.control import Coward, Madman
from truco.agents.human import Human
from truco.agents.player import Grinder, LooseCannon, MaverickBluffer, RationalShark
from truco.agents.spectator import SpectatorAgent
from truco.config import AGENT_PASSWORD, THINK_TIME, XMPP_DOMAIN, SEED
from truco.main import PERSONALITIES, SEATS, play_match  # adjust the import if main.py lives elsewhere
from truco.match_log import setup_console

SPECTATOR_JID = JID(f"spectator@{XMPP_DOMAIN}")
BEHAVIOURS = {c.__name__: c for c in [Grinder, MaverickBluffer, LooseCannon, RationalShark, Coward, Madman]}


class Hub:
    """Keeps every event of the current match so a browser that connects late can replay it."""

    def __init__(self) -> None:
        self.history: list[dict] = []
        self.clients: set[asyncio.Queue] = set()

    async def publish(self, event: dict) -> None:
        # Until the new match-config, whatever arrives is a leftover of the cancelled match
        if not self.history and event.get("event") != "match-config":
            return
        event["seq"] = len(self.history)
        self.history.append(event)
        for queue in self.clients:
            queue.put_nowait(event)

    def reset(self) -> None:
        self.history.clear()


hub = Hub()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.match = None
    app.state.human = None
    app.state.lock = asyncio.Lock()  # one click at a time: cancel the old match, then start the new one
    app.state.spectator = SpectatorAgent(SPECTATOR_JID, AGENT_PASSWORD, hub)
    await app.state.spectator.start()
    yield
    await stop_match()
    await app.state.spectator.stop()


app = FastAPI(lifespan=lifespan)


class MatchRequest(BaseModel):
    lineup: list[str] | None = None  # 4 behaviour names, in seat order A1, B1, A2, B2
    seed: int | None = SEED
    fast: bool = False  # no thinking delay
    seat: Literal["A1", "B1", "A2", "B2"] | None = None  # where the person sits; None = only watch


class ActionRequest(BaseModel):
    """The person's choice for the pending prompt. Only the fields of that kind matter."""

    kind: Literal["turn", "response", "talk"]
    card: str | None = None
    call: bool = False
    response: str | None = None
    action: str | None = None
    value: str | None = None


async def _run(lineup, seed, think_time) -> None:
    try:
        await play_match(
            lineup, seed, think_time, save_log=False, spectator=SPECTATOR_JID,
            on_setup=lambda cfg: hub.publish({"event": "match-config", "seed": seed, **cfg}),
        )
    except Exception as exc:
        await hub.publish({"event": "match-error", "message": repr(exc)})


async def stop_match() -> None:
    """Cancels the running match and waits until its agents are gone (play_match stops them)."""
    task = app.state.match
    if task is not None and not task.done():
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    app.state.match = None
    app.state.human = None


@app.post("/match")
async def start_match(req: MatchRequest = MatchRequest()):
    """Starts a new match. A match still running is cancelled first: the last click wins."""
    async with app.state.lock:
        return await _start(req)


async def _start(req: MatchRequest) -> dict:
    # The seed fixes the deals and the players' draws; the lineup is drawn anew on every click,
    # so each "Nova partida" brings a different table. Pass `lineup` to repeat one.
    names = req.lineup or [random.choice(PERSONALITIES).__name__ for _ in range(4)]
    if len(names) != 4 or any(n not in BEHAVIOURS for n in names):
        raise HTTPException(422, f"lineup precisa de 4 nomes entre {list(BEHAVIOURS)}")
    lineup: list = [BEHAVIOURS[n] for n in names]
    human = None
    if req.seat is not None:
        human = Human(hub.publish)
        lineup[SEATS.index(req.seat)] = human
        names[SEATS.index(req.seat)] = Human.__name__

    await stop_match()
    app.state.human = human
    hub.reset()
    app.state.match = asyncio.create_task(
        _run(lineup, req.seed, None if req.fast else THINK_TIME)
    )
    return {"lineup": names, "seed": req.seed}


@app.post("/action")
async def act(req: ActionRequest):
    """Delivers the person's choice to their seat."""
    human: Human | None = app.state.human
    if human is None:
        raise HTTPException(409, "Você não está jogando nesta partida.")
    error = human.answer(req.model_dump())
    if error is not None:
        raise HTTPException(409, error)
    return {"ok": True}


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    # Subscribe and copy the history with no await in between: nothing is lost or repeated.
    # The history goes in one message, so the browser shows the current state at once
    # instead of replaying the whole match as if it were starting now.
    queue: asyncio.Queue = asyncio.Queue()
    hub.clients.add(queue)
    history = list(hub.history)

    async def forward() -> None:
        await websocket.send_json({"event": "history", "events": history})
        while True:
            await websocket.send_json(await queue.get())

    sender = asyncio.create_task(forward())
    try:
        # The browser never sends anything, but reading is the only way to notice it left.
        # Without it this handler would wait on the queue forever, and uvicorn would hang on
        # Ctrl+C waiting for it, still holding port 5222 for the next start.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        hub.clients.discard(queue)


async def main() -> None:
    await uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000)).serve()


def _port_in_use(port: int) -> bool:
    # Tries to reserve the port instead of connecting to it: under WSL's mirrored networking a
    # connect to a free port hangs until the TCP timeout, while bind answers immediately
    with socket.socket() as s:
        # SO_REUSEADDR: ignore sockets left in TIME_WAIT by a server that just stopped
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:  # EADDRINUSE: someone is already listening here
            return True
        return False


def run() -> None:
    # SPADE swallows these errors, and the browser would just wait forever for a backend that never came up
    for port, what in ((5222, "XMPP"), (8000, "HTTP")):
        if _port_in_use(port):
            sys.exit(f"Porta {port} ({what}) já está em uso: há outro truco-server rodando? Encerre-o e tente de novo.")
    setup_console()
    spade.run(main(), embedded_xmpp_server=True)


if __name__ == "__main__":
    run()
