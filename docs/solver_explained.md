# How the solver works

This is a plain-English explanation of the deduction engine and probability
calculations — the same reasoning the in-app "why?" explanations draw on.

## The puzzle, restated

There are 21 cards (6 suspects, 6 weapons, 9 rooms in the classic edition).
Exactly one card of each category is secretly in the envelope; the other 18
are dealt out among the players. Every card has exactly one "owner": a
specific player, or the envelope. The app's job is to figure out, for each
card, who that owner is — using only what you directly know (your own hand)
and what you can infer from suggestions made around the table.

## Step 1: constraint propagation

Every fact you log becomes one of four constraint types:

- **Owned** — a specific player (or the envelope) definitely holds this card.
- **Not owned** — a specific player definitely does *not* hold this card.
  (E.g., every player asked a suggestion who showed nothing doesn't hold any
  of the three cards suggested.)
- **At least one of** — a player holds *at least one* of three named cards,
  but you don't know which. (This happens when someone shows a card to
  *another* player, not to you — you only see that a card was shown, not
  which one.)
- **Hand size** — how many cards a player's hand holds in total.

The engine repeatedly applies simple rules until nothing more can be
deduced this way:

- If a card's only remaining possible owner is one specific player (every
  other owner has been ruled out), it's confirmed to them.
- If a player's hand is already full of confirmed cards, they can't hold
  anything else — so they're ruled out for every other card.
- If exactly one card of a category (suspect/weapon/room) hasn't been ruled
  out of the envelope, it must be the envelope's card for that category.
- If an "at least one of {A, B, C}" fact has two of the three already ruled
  out for that player, the third one must be theirs.

## Step 2: what propagation alone can't do

Sometimes several "at least one of" facts, combined with hand-size limits,
force a conclusion that none of the rules above catches individually — the
proof only works when you consider all the facts *together*. For this, the
engine falls back to genuinely trying every remaining possible arrangement of
just the still-undetermined cards (there are usually only a handful left by
this point) and checks: does *every* valid arrangement agree on who owns this
card? If so, it's confirmed — even though no single short chain of reasoning
explains it on its own. The app labels this kind of confirmation as a "world
argument" rather than a chain of eliminations, so you can tell the two apart.

## Probabilities: exact, not guessed

For every card that's still ambiguous, the app can tell you exactly what
fraction of all remaining valid arrangements would place it in the envelope.
It does this the same way as step 2 — by considering every valid arrangement
of the still-undetermined cards — except instead of stopping once a single
owner is confirmed, it counts *how many* valid arrangements assign each card
to each possible owner, and divides by the total. This is why the
probabilities the app shows are exact percentages of logically possible
worlds, never a statistical guess.

Because trying every arrangement could be enormous before any suggestions
have narrowed things down, the app only attempts this once few enough cards
remain ambiguous — otherwise it tells you plainly that there isn't enough
information yet, rather than freezing or making something up.

## The advisor: what to suggest next

For each candidate suggestion still worth asking about, the app estimates
how much it would narrow things down: for every way players might respond
(nobody shows, or a specific player shows), it works out how likely that
response is given everything currently known, and how many of the remaining
valid arrangements that response would rule out. Weighting each possible
response by its likelihood gives an "expected fraction of remaining
possibilities eliminated" — which is what's shown as the suggestion's
rationale. To keep this fast, the app first narrows ~300 possible
suggestions down to the most promising handful using a cheaper rule of thumb,
then only fully works out the expected gain for those.

## Contradiction detection

If the facts you've logged can no longer describe any valid game at all —
for example, if a mistake makes some card that would need an owner logically
own none, or a player would need to hold more cards than they physically
have — the app raises a clear error explaining what's wrong, rather than
producing a silently broken deduction. Editing or deleting a past suggestion
never leaves the app in that broken state either: the edit is checked *before*
it replaces your real game, so if it doesn't check out, your existing game is
left exactly as it was.
