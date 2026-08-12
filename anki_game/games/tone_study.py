"""Tone Study: untimed, deliberate tone practice -- the counterpart to Tone
Drill's speed drill. Get a tone wrong and you must retype it correctly
before moving on (active recall of the correction, not just glancing at an
answer that flashes by), and a missed word resurfaces again a few words
later in the same session so the correction gets reinforced while it's
still fresh, instead of maybe not showing up again for a long time."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Label, Static

from anki_game.anki_source import Deck
from anki_game.progress import ProgressStore
from anki_game.queue import WordQueue
from anki_game.words import (
    MODE_TONE,
    TONE_LEGEND,
    Word,
    answer_hint,
    prompt_text,
    tone_pattern,
    tone_shapes,
)

from .base import GameScreen, deck_label

TARGET_WORDS = 12
REINFORCE_AFTER = 5


class ToneStudyScreen(GameScreen):
    DEFAULT_CSS = (
        GameScreen.DEFAULT_CSS
        + """
    #legend, #prompt, #progress {
        content-align: center middle;
    }
    #prompt {
        text-style: bold;
        height: 3;
    }
    """
    )

    def __init__(self, *, deck: Deck, queue: WordQueue, progress: ProgressStore):
        super().__init__(
            deck=deck, queue=queue, progress=progress, game_name="tone_study", mode=MODE_TONE
        )
        self.mastered_count = 0
        self.reinforced_count = 0
        self._pending: list[list] = []  # [countdown, word], words due for another look
        self._needs_reinforcement = False
        self._last_feedback = ""

    def compose_game(self) -> ComposeResult:
        yield Label(f"Tone Study — {deck_label(self.deck)}", id="deck-title")
        yield Static(TONE_LEGEND, id="legend")
        yield Static(id="prompt")
        yield Static(id="progress")
        yield Static(id="status")

    def next_word(self) -> None:
        for entry in self._pending:
            entry[0] -= 1
        self._needs_reinforcement = False
        due_index = next((i for i, e in enumerate(self._pending) if e[0] <= 0), None)
        if due_index is not None:
            _, word = self._pending.pop(due_index)
            self.current = word
            self.show_word(word)
        else:
            super().next_word()

    def show_word(self, word: Word) -> None:
        self.query_one("#prompt", Static).update(f"[bold]{prompt_text(word, self.mode)}[/]")
        progress_line = f"mastered {self.mastered_count}/{TARGET_WORDS}"
        if self._pending:
            progress_line += f"  ·  {len(self._pending)} queued for another look"
        self.query_one("#progress", Static).update(progress_line)
        self.query_one("#status", Static).update(self._last_feedback)

    def on_correct(self, word: Word, guess: str) -> None:
        self.mastered_count += 1
        self.score = self.mastered_count
        pattern = tone_pattern(word.pinyin_variants[0][1])
        self._last_feedback = (
            f"[green]✓ Correct — {word.pinyin_display} = {pattern} ({tone_shapes(pattern)})[/]"
        )
        if self._needs_reinforcement:
            self.reinforced_count += 1
            self._pending.append([REINFORCE_AFTER, word])
        if self.mastered_count >= TARGET_WORDS:
            self.end_session(
                "\U0001f393 Session complete",
                [
                    f"Words mastered: {self.mastered_count}",
                    f"Needed a second look: {self.reinforced_count}",
                ],
            )
            return
        self.next_word()

    def on_incorrect(self, word: Word, guess: str) -> None:
        self._needs_reinforcement = True
        self._last_feedback = (
            f"[red]Not quite -- it's {answer_hint(word, self.mode)}. Type it again:[/]"
        )
        self.show_word(word)
