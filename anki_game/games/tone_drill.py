"""Tone Drill: rapid-fire tone-only quiz. See the Hanzi, type just the tone
number sequence (23 for 小姐, 5 = neutral) before the timer runs out. Always
uses MODE_TONE regardless of which Read/Write/Speak deck you drilled down
through -- tone recall is orthogonal to that split, and the underlying words
are the same Anki notes either way. Isolating just the tone (instead of full
pinyin, as in Speak mode) targets tone recall specifically, and the time
pressure pushes toward instinct over careful recall."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.timer import Timer
from textual.widgets import Label, Static

from anki_game.anki_source import Deck
from anki_game.progress import ProgressStore
from anki_game.queue import WordQueue
from anki_game.words import MODE_TONE, TONE_LEGEND, Word, answer_hint, prompt_text

from .base import GameScreen, bar, deck_label

TICKS_PER_SECOND = 10
SPEEDUP_EVERY = 5
SPEEDUP_FACTOR = 0.9
MAX_LIVES = 3

# difficulty key -> (label, starting seconds per word, floor seconds per word
# once it's sped up from streak bonuses)
DIFFICULTIES = {
    "easy": ("Easy", 6.0, 3.0),
    "medium": ("Medium", 4.0, 1.5),
    "hard": ("Hard", 2.5, 1.0),
}
DEFAULT_DIFFICULTY = "medium"


class ToneDrillScreen(GameScreen):
    DEFAULT_CSS = (
        GameScreen.DEFAULT_CSS
        + """
    #legend, #prompt, #timer-bar {
        content-align: center middle;
    }
    #prompt {
        text-style: bold;
        height: 3;
    }
    """
    )

    def __init__(
        self,
        *,
        deck: Deck,
        queue: WordQueue,
        progress: ProgressStore,
        difficulty: str = DEFAULT_DIFFICULTY,
    ):
        super().__init__(
            deck=deck, queue=queue, progress=progress, game_name="tone_drill", mode=MODE_TONE
        )
        label, start_time_limit, min_time_limit = DIFFICULTIES[difficulty]
        self.difficulty_label = label
        self.min_time_limit = min_time_limit
        self.lives = MAX_LIVES
        self.streak = 0
        self.best_streak = 0
        self.time_limit = start_time_limit
        self.time_left = start_time_limit
        self._timer: Timer | None = None
        self._last_feedback = ""

    def compose_game(self) -> ComposeResult:
        yield Label(
            f"Tone Drill ({self.difficulty_label}) — {deck_label(self.deck)}", id="deck-title"
        )
        yield Static(TONE_LEGEND, id="legend")
        yield Static(id="prompt")
        yield Static(id="timer-bar")
        yield Static(id="status")

    def on_mount(self) -> None:
        super().on_mount()
        self._timer = self.set_interval(1 / TICKS_PER_SECOND, self._tick)

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()

    def next_word(self) -> None:
        self.time_left = self.time_limit
        super().next_word()

    def show_word(self, word: Word) -> None:
        self.query_one("#prompt", Static).update(f"[bold]{prompt_text(word, self.mode)}[/]")
        self._render_timer()
        status = f"lives {'❤ ' * self.lives}· streak {self.streak} · score {self.score}"
        if self._last_feedback:
            status = f"{self._last_feedback}\n{status}"
        self.query_one("#status", Static).update(status)

    def _render_timer(self) -> None:
        self.query_one("#timer-bar", Static).update(
            f"{bar(self.time_left, self.time_limit)} {max(0.0, self.time_left):0.1f}s"
        )

    def _tick(self) -> None:
        if self.current is None or self._ended:
            return
        self.time_left -= 1 / TICKS_PER_SECOND
        if self.time_left <= 0:
            word = self.current
            self.progress.record_answer(word.note_id, False)
            self._miss(word, timeout=True)
        else:
            self._render_timer()

    def on_correct(self, word: Word, guess: str) -> None:
        speed_bonus = round(10 * max(0.0, self.time_left) / self.time_limit)
        points = 10 + speed_bonus
        self.score += points
        self.streak += 1
        self.best_streak = max(self.best_streak, self.streak)
        self._last_feedback = f"[green]✓ +{points}[/]"
        if self.streak % SPEEDUP_EVERY == 0:
            self.time_limit = max(self.min_time_limit, self.time_limit * SPEEDUP_FACTOR)
        self.next_word()

    def on_incorrect(self, word: Word, guess: str) -> None:
        self._miss(word, timeout=False)

    def _miss(self, word: Word, *, timeout: bool) -> None:
        self.lives -= 1
        self.streak = 0
        reason = "Too slow" if timeout else "Wrong"
        self._last_feedback = f"[red]✗ {reason}! It was {answer_hint(word, self.mode)}[/]"
        if self.lives <= 0:
            if self._timer:
                self._timer.stop()
            self.end_session(
                "\U0001f480 Out of lives",
                [f"Best streak: {self.best_streak}", f"Final score: {self.score}"],
            )
            return
        self.next_word()
