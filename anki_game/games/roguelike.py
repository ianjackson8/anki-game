"""Roguelike Map: walk a linear dungeon of rooms. Answer a few words
correctly to clear each room and move to the next; wrong answers cost one
of a shared pool of lives for the whole run. Clear every room to win."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Label, Static

from anki_game.anki_source import Deck
from anki_game.progress import ProgressStore
from anki_game.queue import WordQueue
from anki_game.words import Word, answer_hint, prompt_text

from .base import GameScreen, deck_label

ROOM_COUNT = 6
WORDS_PER_ROOM = 3
MAX_LIVES = 3
ROOM_CLEAR_BONUS = 50
VICTORY_BONUS = 200


def _render_map(current_room: int, room_count: int) -> str:
    cells = []
    for i in range(room_count):
        if i < current_room:
            cells.append("[✓]")
        elif i == current_room:
            cells.append("[●]")
        else:
            cells.append("[ ]")
    return "\U0001f3f0  " + "──".join(cells) + "  \U0001f3c6"


class RoguelikeScreen(GameScreen):
    DEFAULT_CSS = (
        GameScreen.DEFAULT_CSS
        + """
    #map, #room-info, #prompt {
        content-align: center middle;
    }
    #prompt {
        text-style: bold;
        height: 3;
    }
    """
    )

    def __init__(self, *, deck: Deck, queue: WordQueue, progress: ProgressStore, mode: str):
        super().__init__(
            deck=deck, queue=queue, progress=progress, game_name="roguelike", mode=mode
        )
        self.current_room = 0
        self.room_progress = 0
        self.lives = MAX_LIVES
        self._last_feedback = ""

    def compose_game(self) -> ComposeResult:
        yield Label(f"Roguelike Map — {deck_label(self.deck)}", id="deck-title")
        yield Static(id="map")
        yield Static(id="room-info")
        yield Static(id="prompt")
        yield Static(id="status")

    def show_word(self, word: Word) -> None:
        self.query_one("#map", Static).update(_render_map(self.current_room, ROOM_COUNT))
        self.query_one("#room-info", Static).update(
            f"Room {self.current_room + 1}/{ROOM_COUNT}  ·  "
            f"{self.room_progress}/{WORDS_PER_ROOM} solved  ·  "
            f"lives {'❤ ' * self.lives}·  score {self.score}"
        )
        self.query_one("#prompt", Static).update(f"[bold]{prompt_text(word, self.mode)}[/]")
        self.query_one("#status", Static).update(self._last_feedback)

    def on_correct(self, word: Word, guess: str) -> None:
        self.score += 10
        self.room_progress += 1
        if self.room_progress >= WORDS_PER_ROOM:
            self.score += ROOM_CLEAR_BONUS
            self.current_room += 1
            self.room_progress = 0
            if self.current_room >= ROOM_COUNT:
                self.score += VICTORY_BONUS
                self.end_session(
                    "\U0001f3c6 Dungeon cleared!",
                    [f"Rooms cleared: {ROOM_COUNT}/{ROOM_COUNT}", f"Final score: {self.score}"],
                )
                return
            self._last_feedback = "[green]✓ Room cleared! Moving on...[/]"
        else:
            self._last_feedback = f"[green]✓ Correct! ({self.room_progress}/{WORDS_PER_ROOM})[/]"
        self.next_word()

    def on_incorrect(self, word: Word, guess: str) -> None:
        self.lives -= 1
        answer = answer_hint(word, self.mode)
        self._last_feedback = f"[red]✗ It was '{answer}' — {self.lives} lives left[/]"
        if self.lives <= 0:
            self.end_session(
                "\U0001f480 You perished",
                [
                    f"Reached room {self.current_room + 1}/{ROOM_COUNT}",
                    f"Final score: {self.score}",
                ],
            )
            return
        self.next_word()
