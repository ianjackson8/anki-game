"""Dungeon Crawler: each word is an enemy. Correct answers land an attack
that scales with your combo streak; wrong answers let the enemy hit back.
Every few kills spawns a tougher boss, drawn preferentially from words
you've historically gotten wrong (leeches)."""

from __future__ import annotations

import random

from textual.app import ComposeResult
from textual.widgets import Label, Static

from anki_game.anki_source import Deck
from anki_game.progress import ProgressStore
from anki_game.queue import WordQueue
from anki_game.words import Word, answer_hint, prompt_text

from .base import GameScreen, bar, deck_label

PLAYER_MAX_HP = 100
ENEMY_HP = 30
BOSS_HP = 80
ENEMY_COUNTER_DAMAGE = 8
BOSS_COUNTER_DAMAGE = 15
BOSS_EVERY = 5


class DungeonScreen(GameScreen):
    DEFAULT_CSS = (
        GameScreen.DEFAULT_CSS
        + """
    #enemy-name, #prompt, .bar-row {
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
        all_words: list[Word],
        mode: str,
    ):
        super().__init__(
            deck=deck, queue=queue, progress=progress, game_name="dungeon", mode=mode
        )
        self._all_words = all_words
        self.player_hp = PLAYER_MAX_HP
        self.combo = 0
        self.defeated = 0
        self.is_boss = False
        self.enemy_hp = ENEMY_HP
        self.enemy_max_hp = ENEMY_HP
        self._last_feedback = ""

    def compose_game(self) -> ComposeResult:
        yield Label(f"Dungeon Crawler — {deck_label(self.deck)}", id="deck-title")
        yield Static(id="enemy-name")
        yield Static(id="enemy-bar", classes="bar-row")
        yield Static(id="prompt")
        yield Static(id="player-bar", classes="bar-row")
        yield Static(id="status")

    def on_mount(self) -> None:
        self._spawn_enemy()
        super().on_mount()

    def _spawn_enemy(self) -> None:
        self.is_boss = self.defeated > 0 and self.defeated % BOSS_EVERY == 0
        self.enemy_max_hp = BOSS_HP if self.is_boss else ENEMY_HP
        self.enemy_hp = self.enemy_max_hp

    def next_word(self) -> None:
        pool = None
        if self.is_boss:
            leech_ids = self.progress.leech_note_ids()
            candidates = [w for w in self._all_words if w.note_id in leech_ids]
            # Need at least 2 distinct leeches to rotate between, or a boss
            # with only one qualifying word would ask it over and over.
            if len(candidates) >= 2:
                pool = candidates
        if pool:
            # Never immediately repeat the word just shown.
            choices = [w for w in pool if w is not self.current] or pool
            self.current = random.choice(choices)
        else:
            self.current = self.queue.draw()
        self.show_word(self.current)

    def show_word(self, word: Word) -> None:
        name = "\U0001f479 BOSS" if self.is_boss else "\U0001f47e Enemy"
        self.query_one("#enemy-name", Static).update(f"{name}   (defeated {self.defeated})")
        self.query_one("#enemy-bar", Static).update(
            f"HP [red]{bar(max(0, self.enemy_hp), self.enemy_max_hp)}[/] "
            f"{max(0, self.enemy_hp)}/{self.enemy_max_hp}"
        )
        prompt = prompt_text(word, self.mode)
        self.query_one("#prompt", Static).update(f"[bold]{prompt}[/]  ({word.word_type})")
        self.query_one("#player-bar", Static).update(
            f"You [green]{bar(max(0, self.player_hp), PLAYER_MAX_HP)}[/] "
            f"{max(0, self.player_hp)}/{PLAYER_MAX_HP}"
        )
        status = f"combo x{self.combo}  ·  score {self.score}"
        if self._last_feedback:
            status = f"{self._last_feedback}\n{status}"
        self.query_one("#status", Static).update(status)

    def on_correct(self, word: Word) -> None:
        damage = 10 + min(self.combo, 10) * 2
        self.combo += 1
        self.enemy_hp -= damage
        self._last_feedback = f"[green]✓ Hit for {damage}![/]"
        if self.enemy_hp <= 0:
            self.score += 50 if self.is_boss else 10
            self.defeated += 1
            self._spawn_enemy()
        self.next_word()

    def on_incorrect(self, word: Word) -> None:
        self.combo = 0
        dmg = BOSS_COUNTER_DAMAGE if self.is_boss else ENEMY_COUNTER_DAMAGE
        self.player_hp -= dmg
        answer = answer_hint(word, self.mode)
        self._last_feedback = f"[red]✗ It was '{answer}' — you take {dmg} damage[/]"
        if self.player_hp <= 0:
            self.end_session(
                "\U0001f480 You were defeated",
                [f"Enemies defeated: {self.defeated}", f"Final score: {self.score}"],
            )
            return
        self.next_word()
