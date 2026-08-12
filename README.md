# anki-game

Terminal games that study your real Anki flashcards. Reads your Anki collection directly (read-only, never writes to it) and turns due/new cards into gameplay.

Currently ships six games over any `HSK::HSK{1-6}::{Read,Write,Speak}` deck:

- **Dungeon Crawler** — attack a hanzi enemy by answering correctly; miss and it hits back. Every 5 kills spawns a boss drawn from words you've historically struggled with.
- **Typing Attack** — a word falls down a lane each tick; answer before it lands or lose a life. Speed ramps up on a streak.
- **Hanzi Wordle** — hangman-style: the answer is masked and reveals more with each wrong guess, 6 attempts per word, fewer attempts = more points. 10 words per session.
- **Roguelike Map** — walk a 6-room dungeon; answer 3 words correctly to clear a room, wrong answers cost one of your 3 shared lives. Clear every room to reach the treasure.
- **Tone Drill** — Hanzi only, you type just the tone-number sequence (`23` for 小姐) before a shrinking timer runs out. Always tone-only regardless of which Read/Write/Speak deck you picked to get here, since it drills a skill orthogonal to that split. 3 shared lives, speeds up on a streak. Pick Easy (6.0s/word), Medium (4.0s), or Hard (2.5s) before starting — each has its own floor as it speeds up, so Hard never gets easier than 1.0s while Easy bottoms out at 3.0s.
- **Tone Study** — the untimed counterpart to Tone Drill, for actually absorbing a correction instead of just seeing it flash by: get a tone wrong and you must retype it correctly before moving on, and that word resurfaces again ~5 words later in the same session so the correction gets reinforced while it's still fresh. No lives, no timer — just play until you've mastered 12 words (or quit anytime with Escape).

The menu flow is: main menu (shows your overall stats + high scores) → Play → HSK level → Read/Write/Speak → game or **📊 Word stats**. Press Escape from inside a game to jump straight back to the main menu; from a menu screen it backs up one level.

Word stats has three tabs: a **Table** of every word in the deck (worst-accuracy-first), an **Accuracy** bar chart (how many words fall into each accuracy range), and a **By word type** bar chart (accuracy grouped by part of speech, e.g. nouns vs verbs — worst first, needs 2+ practiced words in that type to show up). Correct/wrong counts are shared across Read/Write/Speak, since it's the same underlying Anki note either way.

Each deck variant plays in a different direction, matching what it's meant to drill:

| Deck    | Prompt   | You type       |
|---------|----------|-----------------|
| Read    | Hanzi    | English meaning |
| Speak   | Hanzi    | Pinyin (tones matter) |
| Write   | English  | Hanzi            |

**Pinyin tones**: type either real diacritics (`shén me`) or tone numbers (`shen2 me5`, 5 = neutral) — both are accepted. Tone numbers are the reliable option: diacritic dead-key sequences (e.g. macOS's Option+V then a letter, for the caron/3rd-tone mark) are composed by your terminal emulator and input source *before* this app ever sees a keystroke, so whether they work depends on your terminal + active keyboard layout, not on this app. If they're not working for you, tone numbers always will.

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
```

By default it auto-detects the first Anki profile in the standard per-OS location. If your collection lives somewhere else (or you've cloned this repo on a different machine), copy `config.example.toml` to `config.toml` and set `anki_collection_path` there — `config.toml` is gitignored since the right path is machine-specific.

## Run

```sh
.venv/bin/python -m anki_game
```

**Quit Anki.app before playing** — Anki locks the collection file exclusively while it's open, so this will fail with a clear error (not corrupt anything) if Anki is still running.

Game progress (words practiced, accuracy, high scores) is stored separately in `data/progress.db` and never touches your real Anki collection.

## Adding another game

Subclass `GameScreen` in `anki_game/games/base.py`, implement `compose_game`, `show_word`, `on_correct(word, guess)`, `on_incorrect(word, guess)`, and register it in `GAMES` + `AnkiGameApp.start_game` in `anki_game/app.py`.
