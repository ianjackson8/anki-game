# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [0.2.0] - 2026-08-10

### Added
- **Hanzi Wordle** (`anki_game/games/wordle.py`) — hangman-style progressive reveal: the target answer starts fully masked and reveals more characters with each of up to 6 wrong guesses; score is based on how few attempts you needed. 10 words per session.
- **Roguelike Map** (`anki_game/games/roguelike.py`) — a 6-room linear dungeon with an ASCII map; clear 3 words per room to advance, wrong answers cost one of 3 lives shared across the whole run, clear every room for a victory bonus.
- `anki_game/render.py` — extracted the shared block-bar renderer (`bar()`, used by HP/lives bars and the stats charts) plus a new `bar_chart()` helper, so both games and the stats screen draw from the same place.
- `GameScreen.on_correct`/`on_incorrect` now receive the raw guess text (not just the word), needed for Wordle's guess-history display.
- Typing Attack now shows the correct answer when a word lands unanswered, instead of just silently costing a life.

## [0.1.0] - 2026-08-10

Initial release: terminal games that study your real Anki flashcards.

### Added
- Read-only Anki collection access (`anki_game/anki_source.py`) — never writes to your real collection, auto-detects the standard per-OS Anki profile location, or override via `config.toml`.
- Mode-aware answer checking per deck variant (`anki_game/words.py`, `anki_game/queue.py`): Read = Hanzi → English meaning, Speak = Hanzi → pinyin (tones enforced, numbers or diacritics both accepted), Write = English → Hanzi.
- Due-first word queue (`anki_game/queue.py`) and a local progress store (`anki_game/progress.py`, `data/progress.db`) fully separate from Anki's own data, tracking per-word accuracy and per-game high scores.
- **Dungeon Crawler** (`anki_game/games/dungeon.py`) — battle a hanzi enemy per word; every 5 kills spawns a boss drawn from words you've historically missed.
- **Typing Attack** (`anki_game/games/typing_attack.py`) — words fall down a lane; answer before they land or lose a life, speed ramps on a streak.
- Menu flow (`anki_game/app.py`): main menu with overall stats/high scores → HSK level → Read/Write/Speak → game.
- Word Stats screen: per-deck table (worst-accuracy-first) plus two bar charts — accuracy distribution and accuracy by part of speech.
- `config.example.toml` for pointing at a non-default Anki collection path (e.g. a different machine or OS).

### Fixed
- Meaning matching against Anki's dictionary-style glosses: infinitive/pronoun filler phrases ("to read", "I'm sorry"), comma/semicolon-separated senses without `<li>` tags, and `/`-separated alternatives with no surrounding whitespace all now match a natural learner answer.
- Pinyin matching now accounts for words with more than one valid pronunciation (comma-separated alternates in the source data, e.g. 小姐's colloquial vs. dictionary reading) instead of concatenating them into one unmatchable string.
- Dungeon Crawler boss fights no longer get stuck repeating a single word when only one (or zero) "leech" words qualify — falls back to the full deck, and never immediately repeats a word once there's a real pool to draw from.
- Progress store now uses WAL journal mode for better resilience to concurrent access.
