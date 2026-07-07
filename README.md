# Cluedo Deduction Assistant

A desktop companion app for playing physical Cluedo (Clue). Track players, your
hand, and every suggestion made around the table — including suggestions where
a card is shown to someone *other* than you — and let the app tell you what to
ask next and announce the solution the moment it's logically forced.

Unlike a paper detective sheet, this app runs a real constraint solver: it
performs exact model counting to give you envelope probabilities, explains
*why* every deduction is true, and can simulate hypothetical suggestion
outcomes before you commit to them at the table.

## Features

- Exact constraint propagation + bounded exhaustive search over whatever
  small set of cards propagation alone can't resolve — never guesses.
- Exact envelope probabilities (suspect/weapon/room), derived only from valid
  logical worlds — no sampling or approximation.
- Click any confirmed card to see a plain-English explanation of why it's true.
- Undo, edit, or delete any past suggestion; the whole game state rebuilds
  from scratch so it's always internally consistent.
- Timeline view and step-by-step replay of the whole game.
- What-if mode: simulate a hypothetical outcome without touching your real game.
- An advisor that ranks candidate suggestions by expected information gain —
  how much of the remaining uncertainty a suggestion is likely to resolve.
- Contradiction detection with a clear explanation the moment logged
  information stops being consistent.
- Multiple editions bundled (Swedish 2012 reboot, Classic UK, Classic US), or
  load your own card-set JSON.
- Autosave after every move, with crash recovery on next launch.
- Export the detective sheet to PNG, the timeline to PDF, the full game to
  JSON, or statistics to CSV.
- AI Insights and Endgame panels give rule-based, clearly-labeled-as-advisory
  reads on player behavior and accusation readiness — never presented as
  solver-proven fact.
- Trends charts and a local, opt-out-able cross-game history power richer
  analysis across games, all on-device.
- **Game Review**: an automatic, evidence-based post-game report the moment
  a mystery is solved — difficulty, a letter grade, efficiency versus the
  earliest logically-solvable turn, the game's key turning point and largest
  deduction, missed opportunities the solver can actually prove, and a
  clickable timeline into Replay. Exportable as PDF, HTML, Markdown, or
  JSON. See [docs/game_review_explained.md](docs/game_review_explained.md)
  for how every number is calculated.

## Quickstart

```bash
pip install -r requirements.txt
python main.py
```

Pick your edition, enter the players (in seating order) and hand sizes, select
your own hand, then start logging suggestions as they happen at the table.

## Project layout

See [docs/architecture.md](docs/architecture.md) for the module map, and
[docs/solver_explained.md](docs/solver_explained.md) for how the deduction
engine and probability calculations actually work.

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest
```

See [docs/developer_guide.md](docs/developer_guide.md).
