"""Entry point of the spectator: embedded XMPP server + agents + web server in one event loop."""

import spade
import uvicorn

from truco.match_log import setup_console
from truco.server import app


async def main() -> None:
    await uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000)).serve()


def run() -> None:
    setup_console()
    spade.run(main(), embedded_xmpp_server=True)


if __name__ == "__main__":
    run()