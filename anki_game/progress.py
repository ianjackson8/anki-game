"""Local game progress: per-word accuracy and per-game high scores.

Fully separate from the user's real Anki collection -- this is our own
SQLite file under `data/`, safe to read and write freely.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "progress.db"

@dataclass(frozen=True)
class OverallStats:
    words_practiced: int
    correct: int
    incorrect: int

    @property
    def accuracy_pct(self) -> float:
        total = self.correct + self.incorrect
        return (self.correct / total * 100) if total else 0.0


@dataclass(frozen=True)
class HighScore:
    game: str
    deck_label: str
    score: int


_SCHEMA = """
CREATE TABLE IF NOT EXISTS word_stats (
    note_id INTEGER PRIMARY KEY,
    correct INTEGER NOT NULL DEFAULT 0,
    incorrect INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS high_scores (
    game TEXT NOT NULL,
    deck_label TEXT NOT NULL,
    score INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


class ProgressStore:
    def __init__(self, path: Path | None = None):
        self.path = path or DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.path)
        self._con.execute("PRAGMA journal_mode = WAL")
        self._con.executescript(_SCHEMA)
        self._con.commit()

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> "ProgressStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def record_answer(self, note_id: int, correct: bool) -> None:
        col = "correct" if correct else "incorrect"
        self._con.execute(
            f"""
            INSERT INTO word_stats (note_id, {col}) VALUES (?, 1)
            ON CONFLICT(note_id) DO UPDATE SET {col} = {col} + 1
            """,
            (note_id,),
        )
        self._con.commit()

    def record_score(self, game: str, deck_label: str, score: int) -> None:
        self._con.execute(
            "INSERT INTO high_scores (game, deck_label, score, created_at) VALUES (?, ?, ?, ?)",
            (game, deck_label, score, datetime.now(timezone.utc).isoformat()),
        )
        self._con.commit()

    def best_score(self, game: str, deck_label: str) -> int:
        row = self._con.execute(
            "SELECT MAX(score) FROM high_scores WHERE game = ? AND deck_label = ?",
            (game, deck_label),
        ).fetchone()
        return row[0] or 0

    def overall_stats(self) -> OverallStats:
        words_practiced = self._con.execute("SELECT COUNT(*) FROM word_stats").fetchone()[0]
        correct, incorrect = self._con.execute(
            "SELECT COALESCE(SUM(correct), 0), COALESCE(SUM(incorrect), 0) FROM word_stats"
        ).fetchone()
        return OverallStats(words_practiced=words_practiced, correct=correct, incorrect=incorrect)

    def stats_for_notes(self, note_ids: list[int]) -> dict[int, tuple[int, int]]:
        """note_id -> (correct, incorrect) for whichever of the given notes
        have been played at least once. Note: correct/incorrect are tracked
        per note, not per Read/Write/Speak mode, since all three share the
        same underlying Anki note."""
        if not note_ids:
            return {}
        placeholders = ",".join("?" * len(note_ids))
        rows = self._con.execute(
            f"SELECT note_id, correct, incorrect FROM word_stats WHERE note_id IN ({placeholders})",
            note_ids,
        ).fetchall()
        return {note_id: (correct, incorrect) for note_id, correct, incorrect in rows}

    def top_scores(self) -> list[HighScore]:
        """Best score per game, across all decks ever played."""
        rows = self._con.execute(
            """
            SELECT game, deck_label, MAX(score)
            FROM high_scores
            GROUP BY game
            ORDER BY game
            """
        ).fetchall()
        return [HighScore(game=g, deck_label=d, score=s) for g, d, s in rows]

    def leech_note_ids(self, min_lapses: int = 2) -> set[int]:
        rows = self._con.execute(
            "SELECT note_id FROM word_stats WHERE incorrect >= ?", (min_lapses,)
        ).fetchall()
        return {r[0] for r in rows}
