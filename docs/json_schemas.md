# JSON schemas

## Card-set (edition) config

Used for the bundled editions (`cluedo/data/*.json`) and any custom edition
loaded via "Load custom JSON…".

```json
{
  "edition": "string, display name",
  "suspects": ["exactly 6 unique strings"],
  "weapons": ["exactly 6 unique strings"],
  "rooms": ["exactly 9 unique strings"]
}
```

Rules enforced by `cluedo/config.py`:

- All four keys are required.
- `suspects`, `weapons`, `rooms` must each be non-empty lists of non-empty
  strings.
- No name may repeat, whether within one category or across categories.
- The engine itself doesn't hard-code 6/6/9 — any non-empty split works, but
  the bundled editions and the GUI's hand-size math assume the classic
  21-card, 3-envelope-slot shape.

## Save file

Written by `cluedo.game.save_game`, read by `cluedo.game.load_game`. Also the
format used for autosave and "Export → Full game as JSON".

```json
{
  "save_format_version": 1,
  "card_config": {
    "edition": "string",
    "suspects": ["..."],
    "weapons": ["..."],
    "rooms": ["..."]
  },
  "players": [
    {"name": "string", "seat_index": 0, "hand_size": 6}
  ],
  "user_seat": 0,
  "initial_hand": ["card name", "..."],
  "history": [
    {
      "suggestion_id": "s1",
      "suggester_seat": 0,
      "suspect": "card name",
      "weapon": "card name",
      "room": "card name",
      "responses": [
        {"responder_seat": 1, "outcome": "no_show", "shown_card": null},
        {"responder_seat": 2, "outcome": "shown_to_me", "shown_card": "card name"}
      ]
    }
  ]
}
```

`outcome` is one of `"no_show"`, `"shown_to_me"` (requires `shown_card`), or
`"shown_unseen"` (`shown_card` must be `null`).

`save_format_version` is checked on load; a mismatched version is rejected
with a clear error rather than being replayed incorrectly. Loading replays
`initial_hand` + `history` through a fresh engine rather than deserializing
solver internals directly — the file only ever needs to describe *what
happened*, not *what the engine concluded*, so future engine improvements
stay compatible with old save files.
