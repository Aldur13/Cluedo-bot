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
  possible. Click any cell to see *why* it's confirmed (or hover for a quick
  summary).
- The **Advisor** panel suggests what to ask next, with an estimate of how
  much it should narrow things down.
- The **Envelope probabilities** panel shows the most likely suspect, weapon,
  and room, with exact percentages once enough is known.
- The **Statistics** panel shows how much the solver has figured out and how
  it's spending its effort.

## 6. Undo, edit, or review

- **Undo** (Ctrl+Z) removes the last logged suggestion.
- **Timeline** (Ctrl+E) lists every suggestion; select one to edit or delete
  it — the whole game recomputes from the corrected history.
- **Replay** (Ctrl+R) lets you scrub through the game turn by turn to see
  how the deductions unfolded.
- **What-If** lets you simulate a hypothetical response to a suggestion
  without touching your real game — useful for planning your next move.

## 7. Save, load, export

- **Ctrl+S** / **Ctrl+O** save and load a game file.
- The app **autosaves** after every move and offers to recover it if you
  restart mid-game.
- **Export** lets you save the detective sheet as a PNG, the timeline as a
  PDF, the full game as JSON, or statistics as a CSV.

## 8. Winning

Once the sheet shows all three envelope cards confirmed, a solution banner
appears — that's your accusation.
