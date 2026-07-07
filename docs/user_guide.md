# User guide

## 1. Pick an edition

On launch, choose a bundled edition (Swedish 2012 reboot, Classic UK, Classic
US) or load your own card-set JSON — see [json_schemas.md](json_schemas.md)
for the format if you want to add another edition.

## 2. Set up players

Enter how many people are playing, their names in **seating order** (the order
you go around the table asking suggestions matters for the deduction), and
mark which seat is you. Hand sizes default to an even split of the
non-envelope cards but can be adjusted if your deal was uneven.

## 3. Enter your hand

Check off exactly the cards you were dealt. The app immediately marks these
as known and rules you out as the owner of everything else.

## 4. Log suggestions as they happen

Click **Log Suggestion** (or press Ctrl+N) every time anyone at the table
makes a suggestion. Pick who suggested, the suspect/weapon/room, then for
each other player in turn order:

- **Nobody** — they showed nothing (they hold none of the three).
- **Shows: [card]** — only available when the card was shown *to you*
  (either you asked and saw it, or you were the one showing your own card).
- **Shows a card (unseen)** — someone showed a card to a different player;
  you only know they hold *at least one* of the three, not which.

The dialog stops asking once someone shows a card, matching the real rules.

## 5. Read the sheet

- **Green** = confirmed owner. **Red** = ruled out. **Yellow** = still
  possible. A blue border marks a cell that changed on the most recent turn.
  Click any cell to see *why* it's confirmed (or hover for a quick summary).
- **Best Suggestion** recommends what to ask next, with an estimate of how
  much it should narrow things down.
- **Mystery Progress** shows how much of the deck is known and your estimated
  chance of solving on the next turn.
- **Envelope Probabilities** shows the most likely suspect, weapon, and room,
  with exact percentages once enough is known.
- **AI Insights** offers a rule-based read on each other player's suggestion
  patterns (e.g. "Room Hunter", "Possible Bluffer") — always labeled
  advisory, never presented as a solved fact.
- **Endgame** reports whether it's safe to accuse yet, and if not, how
  confident the solver is in the least-certain category. It never names a
  specific accusation before the mystery is actually solved.
- **Statistics** shows how much the solver has figured out and how it's
  spending its effort.

## 6. Undo, edit, replay, or simulate

- **Undo** (Ctrl+Z) removes the last logged suggestion.
- **Timeline** (Ctrl+E) lists every suggestion; select one to edit or delete
  it — the whole game recomputes from the corrected history.
- **Replay** (Ctrl+R) lets you scrub through the game turn by turn to see
  how the deductions unfolded.
- **What-If** lets you simulate a hypothetical response to a suggestion
  without touching your real game — useful for planning your next move.
- **Trends** charts valid worlds remaining, cards confirmed, and information
  gained per turn across the game so far.
- **Settings** lets you switch theme (Light/Dark/High Contrast) and opt in or
  out of the local cross-game learning that powers AI Insights across games.

## 7. Save, load, export

- **Ctrl+S** / **Ctrl+O** save and load a game file.
- The app **autosaves** after every move and offers to recover it if you
  restart mid-game.
- **Export** lets you save the detective sheet as a PNG, the timeline as a
  PDF, the full game as JSON, or statistics as a CSV.

## 8. Winning

Once the sheet shows all three envelope cards confirmed, a solution banner
appears — that's your accusation.

## 9. Game Review

The moment a game is solved, a **Game Review** opens automatically — a
full post-game report covering difficulty, an overall letter grade, how
efficiently you played versus the earliest point the mystery was logically
solvable, the game's key turning point, best suggestion, and largest single
deduction, any missed opportunities the solver can actually prove (never a
guess), a clickable timeline into Replay, and performance charts.

You can also reopen it any time via the **Review** button, and export it as
PDF, HTML, Markdown, or JSON from inside the screen. See
[game_review_explained.md](game_review_explained.md) for exactly how every
number on the report is calculated.
