"""Read-only access to a real Anki collection.

This module never writes to the user's Anki database. It opens the
collection with SQLite's `mode=ro` URI flag, which raises immediately if a
write is ever attempted, and only issues SELECT statements.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from anki_game.config import configured_collection_path

FIELD_SEP = "\x1f"
DECK_NAME_SEP = "\x1f"

# New/learning/review/relearning card queue types (Anki's `cards.queue`).
QUEUE_NEW = 0
QUEUE_SUSPENDED = -1


def _unicase(a: str, b: str) -> int:
    """Stand-in for Anki's runtime-registered `unicase` collation.

    Anki registers a real Unicode case-insensitive collation via its Rust
    backend; the stdlib sqlite3 driver has no equivalent, so queries that
    touch a `COLLATE unicase` column error out with "no query solution"
    unless something is registered. We only ever read these columns (never
    sort by them for anything that needs to match Anki's exact ordering),
    so a simple casefold comparison is sufficient here.
    """
    fa, fb = a.casefold(), b.casefold()
    return (fa > fb) - (fa < fb)


def _auto_detect_bases() -> list[Path]:
    home = Path.home()
    if sys.platform == "darwin":
        return [home / "Library" / "Application Support" / "Anki2"]
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        return [Path(appdata) / "Anki2"] if appdata else []
    return [home / ".local" / "share" / "Anki2"]


def default_collection_path() -> Path:
    """The configured path (see config.py / config.example.toml) if set,
    otherwise the first collection.anki2 found under the usual per-OS Anki
    profile directory."""
    configured = configured_collection_path()
    if configured is not None:
        if not configured.exists():
            raise FileNotFoundError(
                f"config.toml's anki_collection_path does not exist: {configured}"
            )
        return configured

    for base in _auto_detect_bases():
        candidates = sorted(base.glob("*/collection.anki2"))
        if candidates:
            return candidates[0]
    raise FileNotFoundError(
        "No Anki collection found automatically. Copy config.example.toml to "
        "config.toml and set anki_collection_path to your collection.anki2."
    )


@dataclass(frozen=True)
class Deck:
    id: int
    full_name: str  # e.g. "HSK::HSK1::Read"

    @property
    def parts(self) -> list[str]:
        return self.full_name.split(DECK_NAME_SEP)


@dataclass(frozen=True)
class CardRow:
    id: int
    note_id: int
    deck_id: int
    queue: int
    reps: int
    lapses: int

    @property
    def is_new(self) -> bool:
        return self.queue == QUEUE_NEW


@dataclass(frozen=True)
class NoteRow:
    id: int
    notetype_id: int
    fields: dict[str, str]
    tags: str


class AnkiSource:
    """Read-only handle on a single Anki collection file."""

    def __init__(self, path: Path | None = None):
        self.path = path or default_collection_path()
        uri = f"file:{self.path}?mode=ro"
        self._con = sqlite3.connect(uri, uri=True)
        # Anki opens the collection with an exclusive lock while it runs, so
        # a brief retry window helps if it's mid-shutdown, though normally
        # this means: quit Anki before playing.
        self._con.execute("PRAGMA busy_timeout = 3000")
        self._con.create_collation("unicase", _unicase)
        self._field_names_cache: dict[int, list[str]] = {}
        # Force any lock conflict (e.g. Anki.app has the file open) to
        # surface now rather than deep inside the first real query.
        self._con.execute("SELECT id FROM decks LIMIT 1").fetchone()

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> "AnkiSource":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- decks -----------------------------------------------------------

    def list_decks(self) -> list[Deck]:
        rows = self._con.execute("SELECT id, name FROM decks").fetchall()
        return [Deck(id=did, full_name=name) for did, name in rows]

    def hsk_decks(self) -> list[Deck]:
        """Decks under the top-level 'HSK' deck, e.g. HSK::HSK3::Read."""
        return sorted(
            (d for d in self.list_decks() if d.parts[0] == "HSK" and len(d.parts) == 3),
            key=lambda d: (d.parts[1], d.parts[2]),
        )

    # -- notetype field layout -------------------------------------------

    def field_names(self, notetype_id: int) -> list[str]:
        if notetype_id not in self._field_names_cache:
            rows = self._con.execute(
                "SELECT name FROM fields WHERE ntid = ? ORDER BY ord", (notetype_id,)
            ).fetchall()
            self._field_names_cache[notetype_id] = [r[0] for r in rows]
        return self._field_names_cache[notetype_id]

    # -- cards / notes -----------------------------------------------------

    def cards_in_deck(self, deck_id: int) -> list[CardRow]:
        rows = self._con.execute(
            "SELECT id, nid, did, queue, reps, lapses FROM cards WHERE did = ?",
            (deck_id,),
        ).fetchall()
        return [
            CardRow(id=r[0], note_id=r[1], deck_id=r[2], queue=r[3], reps=r[4], lapses=r[5])
            for r in rows
        ]

    def note(self, note_id: int) -> NoteRow:
        mid, flds, tags = self._con.execute(
            "SELECT mid, flds, tags FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        names = self.field_names(mid)
        values = flds.split(FIELD_SEP)
        fields = dict(zip(names, values))
        return NoteRow(id=note_id, notetype_id=mid, fields=fields, tags=tags)
