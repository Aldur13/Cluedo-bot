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
  ],
  "current_room": "string or null"
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

`current_room` is optional, added in v4.6. It tracks only the app user's
own board position (never other players'), set via
`GameState.set_current_room`. Absent in pre-v4.6 saves, which load with
`current_room: null` — no `save_format_version` bump was needed since it's
purely additive and read via `.get(...)`. A saved room name that no longer
exists in `card_config.rooms` (e.g. a hand-edited or cross-edition file) is
silently dropped back to `null` rather than rejecting the whole file.

## Movement data (board topology)

Bundled per edition under `cluedo/data/movement_<edition_key>.json` (e.g.
`movement_swedish_2012.json`), separate from the card-set config above since
not every edition has a physical board mapped out yet — an edition with no
file simply has no movement/dice features available (loaded via
`cluedo.movement.data.load_movement_data`, which returns `None` for a
missing file, not an error).

```json
{
  "edition_key": "string, must match the bundled edition key (e.g. \"swedish_2012\")",
  "hub": "string, the shared hallway node name",
  "distances_to_hub": {
    "room name": "positive integer tile-distance from that room's entrance to the hub"
  },
  "secret_passages": [["room name", "room name"]],
  "_comment": "optional, ignored by the loader; use it to document how the numbers were derived"
}
```

Rules enforced by `cluedo/movement/data.py`:

- `distances_to_hub` must have exactly one entry per room in the edition's
  `rooms` list — no missing rooms, no extra unknown rooms.
- Every distance must be a positive integer.
- Every `secret_passages` pair must name two distinct, real rooms; no
  duplicate (unordered) pairs.
- Secret passages are modeled as **instant, no-roll** moves (standard
  Cluedo rule) — a room directly connected by a passage from the player's
  current room is 100% reachable every turn regardless of the dice.

The board is modeled as a hub-and-spoke graph (every room connects only to
the shared hallway `hub`, plus zero-weight shortcut edges for secret
passages) — see `cluedo/movement/graph.py` for the shortest-path
computation. This keeps the topology data honest about what's actually
known (rooms open onto one shared hallway) without inventing room-to-room
adjacency that was never confirmed.

### User corrections (v4.6.5+)

The bundled numbers above are photo-derived best-effort estimates, not
measured tile counts. Rather than hand-editing the bundled JSON, the
in-app **Movement Strategy → Edit Board Data** dialog lets the player
correct any distance or add/remove a secret passage directly; saving
writes the *same schema* to a separate, durable per-user file:

```
%APPDATA%\CluedoAssistant\movement_overrides\<edition_key>.json
```

(`cluedo.movement.data.override_path`, mirroring how
`cluedo.game.default_autosave_path` already keeps the autosave outside the
installed app.) This location matters because the packaged `.exe` is a
PyInstaller **onefile** build — `CluedoAssistant.spec` hands `EXE()` the
analysis's `binaries`/`datas` directly rather than routing them through
`COLLECT()`, so the bundled `cluedo/data/*.json` is extracted into a
temporary `_MEI*` directory that's deleted when the process exits. Writing
a correction back into that bundled copy would silently vanish the next
time the app runs; `%APPDATA%` survives across runs.

`cluedo.movement.data.load_movement_data` checks the override file first
and falls back to the bundled default if none exists — an edition with no
bundled file at all can still have movement/dice features once a user
override is saved for it. "Reset to Bundled Defaults" in the dialog just
deletes this override file (`delete_override`).
