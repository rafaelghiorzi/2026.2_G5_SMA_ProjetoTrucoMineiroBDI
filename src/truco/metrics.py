import csv
from pathlib import Path

from slixmpp import JID

FIELDS = ["match", "seed", "point", "round", "player", "personality", "team", "event", "value", "bet"]

class MetricsRecorder:
    def __init__(self, path: str) -> None:
        file = Path(path)
        file.parent.mkdir(parents=True, exist_ok=True)
        is_new = not file.exists()
        self.file = file.open("a", newline="", encoding="utf-8")
        self.writer = csv.writer(self.file)

        if is_new:
            self.writer.writerow(FIELDS)
        self.match = 0
        self.seed: int | None = None
        self.seats: dict[JID, tuple[str, str]] = {}

    def start_match(self, seed: int | None, seats: dict[JID, tuple[str, str]]) -> None:
        """
        Seats: player -> (personality, team)
        """

        self.match += 1
        self.seed = seed
        self.seats = seats

    def event(self, point, round_number, event, player, value, bet) -> None:
        personality, team = self.seats.get(player, ("", ""))
        self.writer.writerow([
            self.match, self.seed, point, round_number,
            player or "", personality, team, event,
            value if value is not None else "",
            bet if bet is not None else "",
        ])

    def close(self) -> None:
        self.file.close()