"""Builds a play session's word supply from a chosen Anki deck.

Due (previously studied) cards are surfaced first, since that's the
strongest signal of what the user actually needs to review right now, then
backfilled with new cards. Once exhausted, the deck reshuffles and repeats
so a session can run as long as the player survives.
"""

from __future__ import annotations

import random

from anki_game.anki_source import AnkiSource, Deck
from anki_game.words import MODE_HANZI, MODE_MEANING, MODE_PINYIN, Word

_DECK_MODE = {
    "Read": MODE_MEANING,  # ZH -> EN
    "Speak": MODE_PINYIN,  # ZH -> pinyin
    "Write": MODE_HANZI,  # EN -> ZH
}


def _hsk_level(deck: Deck) -> int:
    # deck.parts looks like ["HSK", "HSK3", "Read"]
    return int(deck.parts[1].removeprefix("HSK"))


def mode_for_deck(deck: Deck) -> str:
    variant = deck.parts[2]
    try:
        return _DECK_MODE[variant]
    except KeyError:
        raise ValueError(f"unknown deck variant: {variant!r}") from None


def load_words(source: AnkiSource, deck: Deck) -> list[Word]:
    level = _hsk_level(deck)
    words = []
    for card in source.cards_in_deck(deck.id):
        note = source.note(card.note_id)
        words.append(Word.from_card(card, note, hsk_level=level))
    return words


class WordQueue:
    def __init__(self, words: list[Word], rng: random.Random | None = None):
        if not words:
            raise ValueError("WordQueue needs at least one word")
        self._rng = rng or random.Random()
        due = [w for w in words if not w.is_new]
        new = [w for w in words if w.is_new]
        self._rng.shuffle(due)
        self._rng.shuffle(new)
        self._order = due + new
        self._pos = 0

    def __len__(self) -> int:
        return len(self._order)

    def draw(self) -> Word:
        if self._pos >= len(self._order):
            self._rng.shuffle(self._order)
            self._pos = 0
        word = self._order[self._pos]
        self._pos += 1
        return word
