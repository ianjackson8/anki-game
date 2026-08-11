"""Turns raw Anki note fields into a game-friendly Word, plus mode-aware
answer checking (ZH->EN meaning, ZH->pinyin, EN->ZH hanzi)."""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass, field

from anki_game.anki_source import CardRow, NoteRow

_TAG_RE = re.compile(r"<[^>]+>")
_TONE_SPAN_RE = re.compile(r'<span class="tone(\d)">([^<]*)</span>')

MODE_MEANING = "meaning"  # Read: see Hanzi, answer English
MODE_PINYIN = "pinyin"  # Speak: see Hanzi, answer pinyin (tones matter)
MODE_HANZI = "hanzi"  # Write: see English, answer Hanzi


def _strip_html(s: str) -> str:
    unescaped = html.unescape(_TAG_RE.sub(" ", s))
    return " ".join(unescaped.split())


def _strip_diacritics(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _normalize(s: str) -> str:
    s = _strip_diacritics(s).casefold()
    return re.sub(r"[^a-z0-9]+", "", s)


def _normalize_hanzi(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", s.strip()))


def _split_meanings(raw: str) -> list[str]:
    chunks = re.split(r"<li>", raw, flags=re.IGNORECASE)
    tokens: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        clean = _strip_html(chunk)
        for part in re.split(r"[,;]", clean):
            part = part.strip(" .;")
            if part and part.casefold() not in seen:
                seen.add(part.casefold())
                tokens.append(part)
    return tokens


def _parse_pinyin_segment(segment: str) -> tuple[str, str] | None:
    matches = _TONE_SPAN_RE.findall(segment)
    if not matches:
        display = _strip_html(segment)
        return (display, _strip_diacritics(display)) if display else None
    display_parts = []
    numbered_parts = []
    for tone, syllable in matches:
        syllable = html.unescape(syllable).strip()
        if not syllable:
            continue
        display_parts.append(syllable)
        numbered_parts.append(f"{_strip_diacritics(syllable)}{tone}")
    if not display_parts:
        return None
    return " ".join(display_parts), " ".join(numbered_parts)


def _parse_pinyin(raw: str) -> list[tuple[str, str]]:
    """[(display_with_diacritics, tone_numbered), ...], one entry per valid
    pronunciation, e.g. 小姐's colloquial "xiáo jie" / "xiao2 jie5" and
    dictionary "xiǎo jiě" / "xiao3 jie3" -- some words list more than one
    correct reading, comma-separated (not <li> -- that's for meaning senses).

    Anki's own `<span class="toneN">syllable</span>` markup already tells us
    the tone per syllable, which is a far more reliable source than trying
    to re-derive a tone number from a diacritic mark later.
    """
    variants = [_parse_pinyin_segment(seg) for seg in raw.split(",")]
    variants = [v for v in variants if v is not None]
    return variants or [("", "")]


@dataclass(frozen=True)
class Word:
    note_id: int
    card_id: int
    hanzi: str
    traditional: str
    pinyin_variants: list[tuple[str, str]]  # [(display, numbered), ...]
    meanings: list[str] = field(default_factory=list)
    word_type: str = ""
    hsk_level: int = 0
    is_new: bool = True

    @property
    def pinyin_display(self) -> str:
        return self.pinyin_variants[0][0]

    @property
    def pinyin_numbered(self) -> str:
        return self.pinyin_variants[0][1]

    @property
    def pinyin_ascii(self) -> str:
        return _strip_diacritics(self.pinyin_display)

    @property
    def primary_meaning(self) -> str:
        return self.meanings[0] if self.meanings else ""

    @classmethod
    def from_card(cls, card: CardRow, note: NoteRow, hsk_level: int) -> "Word":
        return cls(
            note_id=note.id,
            card_id=card.id,
            hanzi=note.fields.get("Hanzi", "").strip(),
            traditional=note.fields.get("Traditional", "").strip(),
            pinyin_variants=_parse_pinyin(note.fields.get("Pinyin", "")),
            meanings=_split_meanings(note.fields.get("Meaning", "")),
            word_type=note.fields.get("WordType", "").strip(),
            hsk_level=hsk_level,
            is_new=card.is_new,
        )


def _meaning_words(s: str) -> list[str]:
    # "/" separates alternatives without surrounding whitespace, e.g.
    # "books/periodicals/files/etc." -- treat it as a word boundary too, not
    # just whitespace, or it glues into one unmatchable token.
    s = s.replace("/", " ")
    return [w for w in (_normalize(tok) for tok in s.split()) if w]


def _contains_subsequence(haystack: list[str], needle: list[str]) -> bool:
    n = len(needle)
    if n == 0 or n > len(haystack):
        return False
    return any(haystack[i : i + n] == needle for i in range(len(haystack) - n + 1))


def _check_meaning(word: Word, guess: str) -> bool:
    """True if guess's words appear as a contiguous run inside any of the
    word's meanings -- dictionary glosses are often longer/templated than
    what a learner naturally types ("to read" -> "read", "I'm sorry" ->
    "sorry", "a little bit of N" -> "a little bit")."""
    guess_words = _meaning_words(guess)
    if not guess_words:
        return False
    return any(_contains_subsequence(_meaning_words(m), guess_words) for m in word.meanings)


def _check_pinyin(word: Word, guess: str) -> bool:
    """Tone-correct match against any of the word's valid pronunciations.
    Accepts either real diacritics (shén me) or the terminal-safe
    tone-number convention (shen2 me5) -- see note in games/base.py about
    why diacritic dead-key input can be unreliable in a TTY."""
    guess = guess.strip()
    if not guess:
        return False
    guess_numbered = _normalize(guess)  # strips diacritics but keeps digits
    guess_diacritic = " ".join(unicodedata.normalize("NFC", guess).casefold().split())
    for display, numbered in word.pinyin_variants:
        if guess_numbered == _normalize(numbered):
            return True
        target_diacritic = " ".join(unicodedata.normalize("NFC", display).casefold().split())
        if guess_diacritic and guess_diacritic == target_diacritic:
            return True
    return False


def _check_hanzi(word: Word, guess: str) -> bool:
    guess_norm = _normalize_hanzi(guess)
    if not guess_norm:
        return False
    candidates = {word.hanzi, word.traditional} - {""}
    return guess_norm in {_normalize_hanzi(c) for c in candidates}


def check_answer(word: Word, guess: str, mode: str) -> bool:
    if mode == MODE_MEANING:
        return _check_meaning(word, guess)
    if mode == MODE_PINYIN:
        return _check_pinyin(word, guess)
    if mode == MODE_HANZI:
        return _check_hanzi(word, guess)
    raise ValueError(f"unknown answer mode: {mode!r}")


def answer_hint(word: Word, mode: str) -> str:
    """Human-readable 'correct answer was...' text for feedback."""
    if mode == MODE_MEANING:
        return "; ".join(word.meanings) or "?"
    if mode == MODE_PINYIN:
        return " / ".join(f"{display} ({numbered})" for display, numbered in word.pinyin_variants)
    if mode == MODE_HANZI:
        if word.traditional and word.traditional != word.hanzi:
            return f"{word.hanzi} ({word.traditional})"
        return word.hanzi
    raise ValueError(f"unknown answer mode: {mode!r}")


def prompt_text(word: Word, mode: str) -> str:
    """What to show the player to elicit an answer in the given mode."""
    if mode == MODE_HANZI:
        return "; ".join(word.meanings) or word.primary_meaning
    return word.hanzi
