"""Shared building blocks for game screens: the answer-input loop, scoring,
and an end-of-session results screen. Individual games subclass GameScreen
and implement the presentation + win/lose rules.
"""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Input, Label

from anki_game.anki_source import Deck
from anki_game.progress import ProgressStore
from anki_game.queue import WordQueue
from anki_game.render import bar
from anki_game.words import (
    MODE_HANZI,
    MODE_MEANING,
    MODE_PINYIN,
    MODE_TONE,
    Word,
    check_answer,
)

# The mode determines both what's shown as the prompt (see games/dungeon.py,
# games/typing_attack.py) and what the input box expects back.
_PLACEHOLDERS = {
    MODE_MEANING: "type the English meaning, then Enter",
    # Diacritic dead-key input (e.g. macOS's Option+V, e -> "ě") is composed
    # by the OS/terminal before this app ever sees a keystroke, so whether it
    # works depends on your terminal emulator and active input source --
    # tone numbers (shen2 me5) always work and are accepted too.
    MODE_PINYIN: "type pinyin with tones, e.g. shen2 me5 (or shén me), then Enter",
    MODE_HANZI: "type the Hanzi (你好), then Enter",
    MODE_TONE: "type just the tone numbers, e.g. 23 for 小姐 (5 = neutral), then Enter",
}


def deck_label(deck: Deck) -> str:
    return "::".join(deck.parts)


class ResultScreen(Screen):
    DEFAULT_CSS = """
    ResultScreen {
        align: center middle;
    }
    #result-box {
        width: auto;
        min-width: 40;
        border: heavy $accent;
        padding: 1 4;
    }
    #result-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #result-hint {
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, title: str, lines: list[str]):
        super().__init__()
        self._title = title
        self._lines = lines

    def compose(self) -> ComposeResult:
        with Vertical(id="result-box"):
            yield Label(self._title, id="result-title")
            for line in self._lines:
                yield Label(line)
            yield Label("[press any key to return to menu]", id="result-hint")

    def on_key(self, event: events.Key) -> None:
        self.app.pop_screen()


class GameScreen(Screen):
    """Base screen: draws a word, reads a typed answer, dispatches
    on_correct/on_incorrect, and repeats until the game ends."""

    DEFAULT_CSS = """
    GameScreen {
        align: center middle;
    }
    #game-box {
        width: 60;
        height: auto;
    }
    #answer-input {
        margin-top: 1;
    }
    """

    BINDINGS = [Binding("escape", "quit_to_menu", "Main menu", priority=True)]

    def action_quit_to_menu(self) -> None:
        self.app.go_to_main_menu()  # type: ignore[attr-defined]

    def __init__(
        self,
        *,
        deck: Deck,
        queue: WordQueue,
        progress: ProgressStore,
        game_name: str,
        mode: str,
    ):
        super().__init__()
        self.deck = deck
        self.queue = queue
        self.progress = progress
        self.game_name = game_name
        self.mode = mode
        self.current: Word | None = None
        self.score = 0
        self._ended = False

    def compose(self) -> ComposeResult:
        with Vertical(id="game-box"):
            yield from self.compose_game()
            yield Input(placeholder=_PLACEHOLDERS[self.mode], id="answer-input")

    def compose_game(self) -> ComposeResult:  # pragma: no cover - overridden
        raise NotImplementedError

    def on_mount(self) -> None:
        self.next_word()
        self.query_one(Input).focus()

    def next_word(self) -> None:
        self.current = self.queue.draw()
        self.show_word(self.current)

    def show_word(self, word: Word) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._ended or self.current is None:
            return
        guess = event.value
        event.input.value = ""
        correct = check_answer(self.current, guess, self.mode)
        self.progress.record_answer(self.current.note_id, correct)
        if correct:
            self.on_correct(self.current, guess)
        else:
            self.on_incorrect(self.current, guess)

    def on_correct(self, word: Word, guess: str) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def on_incorrect(self, word: Word, guess: str) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def end_session(self, title: str, lines: list[str]) -> None:
        if self._ended:
            return
        self._ended = True
        self.progress.record_score(self.game_name, deck_label(self.deck), self.score)
        best = self.progress.best_score(self.game_name, deck_label(self.deck))
        lines = [*lines, f"Best for this deck: {best}"]
        self.app.pop_screen()
        self.app.push_screen(ResultScreen(title, lines))
