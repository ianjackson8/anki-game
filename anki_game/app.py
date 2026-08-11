"""Textual app shell: main menu (with stats) -> HSK level -> Read/Write/Speak
-> game -> play."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    OptionList,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option

from anki_game.anki_source import AnkiSource, Deck
from anki_game.games.dungeon import DungeonScreen
from anki_game.games.typing_attack import TypingAttackScreen
from anki_game.progress import ProgressStore
from anki_game.queue import WordQueue, load_words, mode_for_deck
from anki_game.render import bar_chart
from anki_game.words import Word

GAMES = {
    "dungeon": ("Dungeon Crawler", "Battle hanzi enemies with typed answers"),
    "typing_attack": ("Typing Attack", "Catch falling words before they land"),
}


def _level_of(deck: Deck) -> int:
    return int(deck.parts[1].removeprefix("HSK"))


class GameMenuScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, deck: Deck):
        super().__init__()
        self.deck = deck

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(
            f"Choose a game — HSK{_level_of(self.deck)} · {self.deck.parts[2]}", id="menu-title"
        )
        options = [Option(f"{name} — {desc}", id=key) for key, (name, desc) in GAMES.items()]
        options.append(Option("📊 Word stats — see how you're doing on this deck", id="stats"))
        yield OptionList(*options, id="game-list")
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id == "stats":
            self.app.show_stats(self.deck)  # type: ignore[attr-defined]
        else:
            self.app.start_game(self.deck, event.option.id)  # type: ignore[attr-defined]


_ACCURACY_BUCKETS = ("Not practiced", "0–40%", "40–70%", "70–100%")


def _accuracy_buckets(words: list[Word], stats: dict[int, tuple[int, int]]) -> dict[str, int]:
    counts = dict.fromkeys(_ACCURACY_BUCKETS, 0)
    for w in words:
        correct, incorrect = stats.get(w.note_id, (0, 0))
        seen = correct + incorrect
        if seen == 0:
            counts["Not practiced"] += 1
        else:
            acc = correct / seen
            counts["70–100%" if acc >= 0.7 else "40–70%" if acc >= 0.4 else "0–40%"] += 1
    return counts


def _accuracy_by_word_type(
    words: list[Word], stats: dict[int, tuple[int, int]], min_practiced: int = 2
) -> list[tuple[str, float, int]]:
    """[(word_type, accuracy_pct, times_seen), ...] for practiced words,
    grouped by the word's primary (first-listed) part of speech, worst
    accuracy first. Types with too few practiced words are dropped as
    too noisy to be meaningful."""
    totals: dict[str, list[int]] = {}
    for w in words:
        correct, incorrect = stats.get(w.note_id, (0, 0))
        seen = correct + incorrect
        if seen == 0:
            continue
        primary = w.word_type.split()[0] if w.word_type.split() else "?"
        bucket = totals.setdefault(primary, [0, 0])
        bucket[0] += correct
        bucket[1] += incorrect

    rows = []
    for word_type, (correct, incorrect) in totals.items():
        seen = correct + incorrect
        if seen < min_practiced:
            continue
        rows.append((word_type, correct / seen * 100, seen))
    rows.sort(key=lambda r: r[1])
    return rows


class StatsScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, *, deck: Deck, words: list[Word], progress: ProgressStore):
        super().__init__()
        self.deck = deck
        self.words = words
        self.progress = progress

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(
            f"Word stats — HSK{_level_of(self.deck)} · {self.deck.parts[2]}", id="menu-title"
        )
        with TabbedContent(initial="table"):
            with TabPane("Table", id="table"):
                yield DataTable(id="stats-table")
            with TabPane("Accuracy", id="chart-accuracy"):
                yield Static(id="chart-accuracy-body")
            with TabPane("By word type", id="chart-wordtype"):
                yield Static(id="chart-wordtype-body")
        yield Footer()

    def on_mount(self) -> None:
        stats = self.progress.stats_for_notes([w.note_id for w in self.words])
        self._build_table(stats)
        self._build_accuracy_chart(stats)
        self._build_wordtype_chart(stats)

    def _build_table(self, stats: dict[int, tuple[int, int]]) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Hanzi", "Pinyin", "Meaning", "Seen", "Correct", "Wrong", "Accuracy")

        rows = []
        for w in self.words:
            correct, incorrect = stats.get(w.note_id, (0, 0))
            seen = correct + incorrect
            rows.append((w, seen, correct, incorrect))

        def sort_key(row):
            _, seen, correct, incorrect = row
            if seen == 0:
                return (1, 0.0)
            return (0, correct / seen)

        rows.sort(key=sort_key)

        for w, seen, correct, incorrect in rows:
            accuracy = f"{correct / seen * 100:.0f}%" if seen else "—"
            table.add_row(
                w.hanzi, w.pinyin_display, w.primary_meaning, str(seen), str(correct),
                str(incorrect), accuracy,
            )
        table.focus()

    def _build_accuracy_chart(self, stats: dict[int, tuple[int, int]]) -> None:
        counts = _accuracy_buckets(self.words, stats)
        deck_size = len(self.words) or 1
        rows = [(label, count, deck_size) for label, count in counts.items()]
        chart = bar_chart(rows, value_fmt="{:.0f}")
        body = (
            f"How many of this deck's {deck_size} words fall into each accuracy range "
            f"(bars scaled to deck size):\n\n{chart}"
        )
        self.query_one("#chart-accuracy-body", Static).update(body)

    def _build_wordtype_chart(self, stats: dict[int, tuple[int, int]]) -> None:
        by_type = _accuracy_by_word_type(self.words, stats)
        widget = self.query_one("#chart-wordtype-body", Static)
        if not by_type:
            widget.update("Not enough practiced words yet to break this down by word type.")
            return
        rows = [(word_type, acc, 100.0) for word_type, acc, _seen in by_type]
        chart = bar_chart(rows, value_fmt="{:.0f}%")
        body = (
            "Accuracy by part of speech (worst first, needs 2+ practiced words "
            "in that type):\n\n" + chart
        )
        widget.update(body)


class VariantMenuScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, level: int, decks: list[Deck]):
        super().__init__()
        self.level = level
        self._decks = [d for d in decks if _level_of(d) == level]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f"HSK{self.level} — Read, Write, or Speak?", id="menu-title")
        options = [Option(d.parts[2], id=str(d.id)) for d in self._decks]
        yield OptionList(*options, id="variant-list")
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        deck = next(d for d in self._decks if str(d.id) == event.option.id)
        self.app.push_screen(GameMenuScreen(deck))


class LevelMenuScreen(Screen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, decks: list[Deck]):
        super().__init__()
        self._decks = decks
        self._levels = sorted({_level_of(d) for d in decks})

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Choose an HSK level", id="menu-title")
        options = [Option(f"HSK{lvl}", id=str(lvl)) for lvl in self._levels]
        yield OptionList(*options, id="level-list")
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.app.push_screen(VariantMenuScreen(int(event.option.id), self._decks))


class MainMenuScreen(Screen):
    BINDINGS = [Binding("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Anki Terminal Games", id="menu-title")
        yield Static(id="stats-box")
        yield OptionList(Option("Play", id="play"), id="main-list")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_stats()

    def on_screen_resume(self) -> None:
        self.refresh_stats()

    def refresh_stats(self) -> None:
        progress: ProgressStore = self.app.progress  # type: ignore[attr-defined]
        stats = progress.overall_stats()
        lines = [
            f"Words practiced: {stats.words_practiced}",
            f"Answers: {stats.correct} correct / {stats.incorrect} wrong "
            f"({stats.accuracy_pct:.0f}% accuracy)",
        ]
        top = progress.top_scores()
        if top:
            lines.append("")
            lines.append("High scores:")
            for hs in top:
                name = GAMES.get(hs.game, (hs.game, ""))[0]
                lines.append(f"  {name}: {hs.score}  ({hs.deck_label})")
        else:
            lines.append("")
            lines.append("No games played yet.")
        self.query_one("#stats-box", Static).update("\n".join(lines))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id == "play":
            decks: list[Deck] = self.app.decks  # type: ignore[attr-defined]
            self.app.push_screen(LevelMenuScreen(decks))


class AnkiGameApp(App):
    TITLE = "Anki Terminal Games"

    def __init__(self, source: AnkiSource, progress: ProgressStore):
        super().__init__()
        self.source = source
        self.progress = progress
        self.decks: list[Deck] = []

    def on_mount(self) -> None:
        self.decks = self.source.hsk_decks()
        self.push_screen(MainMenuScreen())

    def go_to_main_menu(self) -> None:
        """Pop back down to the MainMenuScreen from anywhere in the stack."""
        while len(self.screen_stack) > 2:
            self.pop_screen()

    def start_game(self, deck: Deck, game_key: str) -> None:
        words = load_words(self.source, deck)
        queue = WordQueue(words)
        mode = mode_for_deck(deck)
        if game_key == "dungeon":
            screen = DungeonScreen(
                deck=deck, queue=queue, progress=self.progress, all_words=words, mode=mode
            )
        else:
            screen = TypingAttackScreen(deck=deck, queue=queue, progress=self.progress, mode=mode)
        self.push_screen(screen)

    def show_stats(self, deck: Deck) -> None:
        words = load_words(self.source, deck)
        self.push_screen(StatsScreen(deck=deck, words=words, progress=self.progress))
