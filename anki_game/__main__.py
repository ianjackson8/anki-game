import sqlite3
import sys

from anki_game.anki_source import AnkiSource
from anki_game.app import AnkiGameApp
from anki_game.progress import ProgressStore


def run() -> None:
    try:
        source = AnkiSource()
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc):
            print(
                "Couldn't open your Anki collection -- Anki.app has it locked.\n"
                "Quit Anki and try again.",
                file=sys.stderr,
            )
            sys.exit(1)
        raise
    with source, ProgressStore() as progress:
        AnkiGameApp(source, progress).run()


if __name__ == "__main__":
    run()
