"""HTTP/WebSocket bridge between the spectator agent and the browser.

Entry point of the spectator: embedded XMPP server + agents + web server in one event loop.
"""

import asyncio
import random
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import spade
import uvicorn
from slixmpp import JID

from truco.agents.control import Coward, Madman
from truco.agents.player import Grinder, LooseCannon, MaverickBluffer, RationalShark
from truco.agents.spectator import SpectatorAgent
from truco.config import AGENT_PASSWORD, THINK_TIME, XMPP_DOMAIN
from truco.main import PERSONALITIES, play_match  # adjust the import if main.py lives elsewhere
from truco.match_log import setup_console

SPECTATOR_JID = JID(f"spectator@{XMPP_DOMAIN}")
BEHAVIOURS = {c.__name__: c for c in [Grinder, MaverickBluffer, LooseCannon, RationalShark, Coward, Madman]}


class Hub:
    """Keeps every event of the current match so a browser that connects late can replay it."""

    def __init__(self) -> None:
        self.history: list[dict] = []
        self.clients: set[asyncio.Queue] = set()

    async def publish(self, event: dict) -> None:
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
    app.state.spectator = SpectatorAgent(SPECTATOR_JID, AGENT_PASSWORD, hub)
    await app.state.spectator.start()
    yield
    await app.state.spectator.stop()


app = FastAPI(lifespan=lifespan)


class MatchRequest(BaseModel):
    lineup: list[str] | None = None  # 4 behaviour names, in seat order A1, B1, A2, B2
    seed: int | None = None
    fast: bool = False  # no thinking delay


async def _run(lineup, seed, think_time) -> None:
    try:
        await play_match(
            lineup, seed, think_time, save_log=False, spectator=SPECTATOR_JID,
            on_setup=lambda cfg: hub.publish({"event": "match-config", **cfg}),
        )
    except Exception as exc:
        await hub.publish({"event": "match-error", "message": repr(exc)})


@app.post("/match")
async def start_match(req: MatchRequest = MatchRequest()):
    task = app.state.match
    if task is not None and not task.done():
        raise HTTPException(409, "Já existe uma partida em andamento.")
    names = req.lineup or [random.choice(PERSONALITIES).__name__ for _ in range(4)]
    if len(names) != 4 or any(n not in BEHAVIOURS for n in names):
        raise HTTPException(422, f"lineup precisa de 4 nomes entre {list(BEHAVIOURS)}")
    hub.reset()
    app.state.match = asyncio.create_task(
        _run([BEHAVIOURS[n] for n in names], req.seed, None if req.fast else THINK_TIME)
    )
    return {"lineup": names}


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()
    for event in list(hub.history):
        await websocket.send_json(event)
    hub.clients.add(queue)
    try:
        while True:
            await websocket.send_json(await queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(queue)


async def main() -> None:
    await uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000)).serve()


def run() -> None:
    setup_console()
    spade.run(main(), embedded_xmpp_server=True)


if __name__ == "__main__":
    run()
