"""Development launchers exposed as `uv run` scripts (see [project.scripts] in pyproject.toml).

    uv run truco-serve  -> backend only (XMPP + agents + FastAPI on :8000)
    uv run truco-web    -> frontend only (Vite dev server on :5173, proxies /ws and /match to :8000)
    uv run truco-dev    -> both at once; Ctrl+C stops both
"""

import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

# src/truco/dev.py -> src/frontend
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


def _npm() -> str:
    npm = shutil.which("npm")
    if npm is None:
        sys.exit("npm not found: install Node.js (https://nodejs.org) to run the frontend.")
    return npm


def _ensure_node_modules(npm: str) -> None:
    # node_modules is gitignored, so a fresh clone needs one `npm install` first
    if not (FRONTEND_DIR / "node_modules").exists():
        print("Installing frontend dependencies (npm install)...")
        subprocess.run([npm, "install"], cwd=FRONTEND_DIR, check=True)


def _spawn(cmd: list[str], **kwargs) -> subprocess.Popen:
    # Own process group, so stopping it also stops grandchildren (npm -> sh -> vite)
    return subprocess.Popen(cmd, start_new_session=True, **kwargs)


def _stop(p: subprocess.Popen, sig: int) -> None:
    try:
        os.killpg(p.pid, sig)
    except ProcessLookupError:
        pass


def _frontend_process() -> subprocess.Popen:
    npm = _npm()
    _ensure_node_modules(npm)
    return _spawn([npm, "run", "dev"], cwd=FRONTEND_DIR)


def _backend_process() -> subprocess.Popen:
    # `-m truco.serve` runs serve.py as __main__, so its `if __name__ == "__main__"` guard
    # applies (without it the embedded XMPP server hangs at agent registration)
    return _spawn([sys.executable, "-m", "truco.serve"])


def _raise_interrupt(*_) -> None:
    raise KeyboardInterrupt


def _wait(*procs: subprocess.Popen) -> None:
    """Waits until any process exits (or Ctrl+C / SIGTERM), then stops the others."""
    signal.signal(signal.SIGTERM, _raise_interrupt)  # treat `kill` like Ctrl+C
    try:
        while all(p.poll() is None for p in procs):
            try:
                procs[0].wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            _stop(p, signal.SIGINT)  # same as Ctrl+C: lets uvicorn/SPADE shut down cleanly
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _stop(p, signal.SIGKILL)


def web() -> None:
    _wait(_frontend_process())


def dev() -> None:
    _wait(_backend_process(), _frontend_process())
