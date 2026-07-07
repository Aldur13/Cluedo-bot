"""Loading and validation of card-set configs (editions)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Sequence

from cluedo.models import Card, CardType

BUNDLED_EDITIONS = {
    "swedish_2012": "swedish_reboot_2012.json",
    "classic_uk": "classic_uk.json",
    "classic_us": "classic_us.json",
}

# Board-movement data is bundled per edition, separately from the card-set
# config above, since not every edition has a physical board mapped out yet.
# Absence of an entry here means "no movement data for this edition" -- a
# normal, expected state that callers (cluedo.movement.data) must handle
# gracefully, not an error.
_MOVEMENT_DATA_FILES = {
    "swedish_2012": "movement_swedish_2012.json",
}


def movement_data_filename(edition_key: str) -> str | None:
    """Bundled movement-data filename for this edition key, or None if no
    board has been mapped out for it yet (e.g. classic_uk, classic_us)."""
    return _MOVEMENT_DATA_FILES.get(edition_key)


class ConfigError(ValueError):
    """Raised when a card-set config JSON is malformed or inconsistent."""


@dataclass(frozen=True)
class CardConfig:
    edition: str
    suspects: tuple[str, ...]
    weapons: tuple[str, ...]
    rooms: tuple[str, ...]

    def all_cards(self) -> list[Card]:
        return (
            [Card(name, CardType.SUSPECT) for name in self.suspects]
            + [Card(name, CardType.WEAPON) for name in self.weapons]
            + [Card(name, CardType.ROOM) for name in self.rooms]
        )

    def cards_by_type(self, card_type: CardType) -> tuple[str, ...]:
        return {
            CardType.SUSPECT: self.suspects,
            CardType.WEAPON: self.weapons,
            CardType.ROOM: self.rooms,
        }[card_type]


def _validate(data: dict) -> CardConfig:
    required_keys = {"edition", "suspects", "weapons", "rooms"}
    missing = required_keys - data.keys()
    if missing:
        raise ConfigError(f"card config missing required keys: {sorted(missing)}")

    edition = data["edition"]
    suspects: Sequence[str] = data["suspects"]
    weapons: Sequence[str] = data["weapons"]
    rooms: Sequence[str] = data["rooms"]

    for label, seq in (("suspects", suspects), ("weapons", weapons), ("rooms", rooms)):
        if not isinstance(seq, list) or not all(isinstance(x, str) and x.strip() for x in seq):
            raise ConfigError(f"'{label}' must be a non-empty list of non-empty strings")

    all_names = list(suspects) + list(weapons) + list(rooms)
    if len(all_names) != len(set(all_names)):
        seen = set()
        dupes = set()
        for name in all_names:
            if name in seen:
                dupes.add(name)
            seen.add(name)
        raise ConfigError(f"duplicate card names across/within categories: {sorted(dupes)}")

    if len(all_names) == 0:
        raise ConfigError("card config must define at least one card")

    return CardConfig(
        edition=edition,
        suspects=tuple(suspects),
        weapons=tuple(weapons),
        rooms=tuple(rooms),
    )


def load_card_config(path: Path | str | None = None) -> CardConfig:
    """Load and validate a card config. Defaults to the bundled Swedish 2012 edition."""
    if path is None:
        raw = resources.files("cluedo.data").joinpath("swedish_reboot_2012.json").read_text(encoding="utf-8")
    else:
        raw = Path(path).read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in card config: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("card config JSON must be an object")
    return _validate(data)


def load_bundled_edition(key: str) -> CardConfig:
    if key not in BUNDLED_EDITIONS:
        raise ConfigError(f"unknown bundled edition '{key}', expected one of {sorted(BUNDLED_EDITIONS)}")
    raw = resources.files("cluedo.data").joinpath(BUNDLED_EDITIONS[key]).read_text(encoding="utf-8")
    return _validate(json.loads(raw))


def list_bundled_editions() -> list[tuple[str, str]]:
    """Returns [(key, display_name), ...] for the edition-select screen."""
    result = []
    for key in BUNDLED_EDITIONS:
        cfg = load_bundled_edition(key)
        result.append((key, cfg.edition))
    return result
