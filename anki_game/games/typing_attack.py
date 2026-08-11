"""Typing Attack: one word at a time falls down a lane. Type the pinyin or
meaning and hit Enter before it reaches the bottom, or lose a life. Catches
close to the top score more and speed ramps up on a hot streak."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.timer import Timer
from textual.widgets import Label, Static

from anki_game.anki_source import Deck
from anki_game.progress import ProgressStore
from anki_game.queue import WordQueue
from anki_game.words import Word, prompt_text

from .base import GameScreen, deck_label

LANE_HEIGHT = 10
START_LIVES = 3
START_INTERVAL = 1.0
MIN_INTERVAL = 0.35
SPEEDUP_EVERY = 5
SPEEDUP_FACTOR = 0.9


class TypingAttackScreen(GameScreen):
    DEFAULT_CSS = (
        GameScreen.DEFAULT_CSS
        + f"""
    #lane {{
        height: {LANE_HEIGHT + 2};
        border: round $accent;
    }}
    #status {{
        content-align: center middle;
    }}
    """
    )

    def __init__(self, *, deck: Deck, queue: WordQueue, progress: ProgressStore, mode: str):
        super().__init__(
            deck=deck, queue=queue, progress=progress, game_name="typing_attack", mode=mode
        )
        self.lives = START_LIVES
        self.row = 0
        self.interval = START_INTERVAL
        self.streak = 0
        self._timer: Timer | None = None

    def compose_game(self) -> ComposeResult:
        yield Label(f"Typing Attack — {deck_label(self.deck)}", id="deck-title")
        yield Static(id="lane")
        yield Static(id="status")

    def on_mount(self) -> None:
        super().on_mount()
        self._timer = self.set_interval(self.interval, self._tick)

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()

    def next_word(self) -> None:
        self.row = 0
        super().next_word()

    def show_word(self, word: Word) -> None:
        self._render_lane(word)
        speed = START_INTERVAL / self.interval
        self.query_one("#status", Static).update(
            f"lives {'❤ ' * self.lives}· score {self.score} · speed {speed:.1f}x"
        )

    def _render_lane(self, word: Word) -> None:
        text = prompt_text(word, self.mode)
        lines = ["   " + (text if r == self.row else "") for r in range(LANE_HEIGHT)]
        lines.append("─" * 16)
        self.query_one("#lane", Static).update("\n".join(lines))

    def _tick(self) -> None:
        if self.current is None:
            return
        self.row += 1
        if self.row >= LANE_HEIGHT:
            self._land()
        else:
            self._render_lane(self.current)

    def _land(self) -> None:
        self.lives -= 1
        self.streak = 0
        if self.lives <= 0:
            if self._timer:
                self._timer.stop()
            self.end_session("\U0001f4a5 Game over", [f"Final score: {self.score}"])
            return
        self.next_word()

    def on_correct(self, word: Word) -> None:
        distance_left = LANE_HEIGHT - self.row
        self.score += 10 + distance_left
        self.streak += 1
        if self.streak % SPEEDUP_EVERY == 0:
            self.interval = max(MIN_INTERVAL, self.interval * SPEEDUP_FACTOR)
            if self._timer:
                self._timer.stop()
            self._timer = self.set_interval(self.interval, self._tick)
        self.next_word()

    def on_incorrect(self, word: Word) -> None:
        self.query_one("#status", Static).update(
            f"lives {'❤ ' * self.lives}· score {self.score} · not quite, keep trying..."
        )
