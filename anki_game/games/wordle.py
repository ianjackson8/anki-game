"""Hanzi Wordle: a hangman-style guessing game. Each round shows the usual
prompt (Hanzi, or the English meaning for Write mode) plus a masked target
answer that reveals more letters with every wrong guess. You get 6 attempts
per word; fewer attempts used scores more. Ten words per session."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Label, Static

from anki_game.anki_source import Deck
from anki_game.progress import ProgressStore
from anki_game.queue import WordQueue
from anki_game.words import MODE_HANZI, MODE_MEANING, MODE_PINYIN, Word, answer_hint, prompt_text

from .base import GameScreen, deck_label

MAX_ATTEMPTS = 6
ROUNDS_PER_SESSION = 10


def _target_string(word: Word, mode: str) -> str:
    if mode == MODE_MEANING:
        return word.primary_meaning
    if mode == MODE_PINYIN:
        return word.pinyin_display
    return word.hanzi  # MODE_HANZI


def _mask(target: str, wrong_attempts: int, max_attempts: int) -> str:
    """Hangman-style progressive reveal: more of the target's characters
    (in order) become visible with each wrong guess, spaces stay visible as
    structural hints."""
    if not target:
        return ""
    reveal_count = min(len(target), round(len(target) * wrong_attempts / max_attempts))
    cells = [ch if (ch.isspace() or i < reveal_count) else "_" for i, ch in enumerate(target)]
    return " ".join(cells)


class WordleScreen(GameScreen):
    DEFAULT_CSS = (
        GameScreen.DEFAULT_CSS
        + """
    #round-info, #prompt, #clue {
        content-align: center middle;
    }
    #prompt {
        text-style: bold;
        height: 3;
    }
    #clue {
        text-style: bold;
    }
    """
    )

    def __init__(self, *, deck: Deck, queue: WordQueue, progress: ProgressStore, mode: str):
        super().__init__(deck=deck, queue=queue, progress=progress, game_name="wordle", mode=mode)
        self.round_number = 0
        self.wrong_attempts = 0
        self.guess_history: list[str] = []
        self.solved_count = 0
        self._last_feedback = ""

    def compose_game(self) -> ComposeResult:
        yield Label(f"Hanzi Wordle — {deck_label(self.deck)}", id="deck-title")
        yield Static(id="round-info")
        yield Static(id="prompt")
        yield Static(id="clue")
        yield Static(id="status")

    def next_word(self) -> None:
        self.round_number += 1
        if self.round_number > ROUNDS_PER_SESSION:
            self.end_session(
                "\U0001f3c1 Session complete",
                [
                    f"Solved: {self.solved_count}/{ROUNDS_PER_SESSION}",
                    f"Final score: {self.score}",
                ],
            )
            return
        self.wrong_attempts = 0
        self.guess_history = []
        super().next_word()

    def show_word(self, word: Word) -> None:
        self.query_one("#round-info", Static).update(
            f"Round {self.round_number}/{ROUNDS_PER_SESSION}  ·  "
            f"HSK{word.hsk_level} · {word.word_type}  ·  "
            f"attempts left: {MAX_ATTEMPTS - self.wrong_attempts}/{MAX_ATTEMPTS}  ·  "
            f"score {self.score}"
        )
        self.query_one("#prompt", Static).update(f"[bold]{prompt_text(word, self.mode)}[/]")
        target = _target_string(word, self.mode)
        self.query_one("#clue", Static).update(_mask(target, self.wrong_attempts, MAX_ATTEMPTS))
        lines = []
        if self._last_feedback:
            lines.append(self._last_feedback)
        if self.guess_history:
            lines.append("tried: " + ", ".join(self.guess_history))
        self.query_one("#status", Static).update("\n".join(lines))

    def on_correct(self, word: Word, guess: str) -> None:
        points = MAX_ATTEMPTS - self.wrong_attempts
        self.score += points
        self.solved_count += 1
        self._last_feedback = (
            f"[green]✓ Solved in {self.wrong_attempts + 1} guess"
            f"{'es' if self.wrong_attempts else ''}! +{points}[/]"
        )
        self.next_word()

    def on_incorrect(self, word: Word, guess: str) -> None:
        self.wrong_attempts += 1
        if guess.strip():
            self.guess_history.append(guess.strip())
        if self.wrong_attempts >= MAX_ATTEMPTS:
            self._last_feedback = f"[red]✗ Out of guesses -- it was {answer_hint(word, self.mode)}[/]"
            self.next_word()
            return
        self.show_word(word)
