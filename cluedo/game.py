"""GameState: the facade the GUI talks to. Orchestrates the engine, history
replay, probabilities, and explanations behind one object, and owns the
atomic build-candidate-then-swap-on-success pattern used by every mutation
(initial hand, new suggestion, undo, edit, delete) so a logically invalid
edit can never corrupt the live game."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cluedo.config import CardConfig
from cluedo.engine import ConstraintEngine, ContradictionError, SolverStats
from cluedo.explain import Explanation, FactSource, full_derivation_chain
from cluedo.models import ENVELOPE, Card, Player, Suggestion, SuggestionResponse, seat_id
from cluedo.probability import full_probabilities

SAVE_FORMAT_VERSION = 1


class SaveFileError(Exception):
    pass


class GameState:
    def __init__(self, config: CardConfig, players: list[Player], user_seat: int):
        self.config = config
        self.players = players
        self.user_seat = user_seat
        self.cards = config.all_cards()
        self.history: list[Suggestion] = []
        self._initial_hand: list[Card] = []
        self._next_suggestion_id = 1
        self.engine = ConstraintEngine(self.cards, players)

    # ---------------------------------------------------------- construction

    @classmethod
    def from_history(
        cls,
        config: CardConfig,
        players: list[Player],
        user_seat: int,
        initial_hand: list[Card],
        history: list[Suggestion],
    ) -> "GameState":
        """The one shared rebuild-from-scratch primitive: constructs a fresh
        engine and replays the initial hand + every suggestion in order through
        it. Raises ContradictionError (uncaught) if the given history is not
        internally consistent -- callers use this as their validation gate
        before committing to it as the live state."""
        gs = cls(config, players, user_seat)
        gs._initial_hand = list(initial_hand)
        gs._apply_initial_hand_facts()
        gs.engine.recompute()
        for suggestion in history:
            gs._apply_suggestion_facts(suggestion)
            gs.engine.recompute()
        gs.history = list(history)
        used_ids = [int(s.suggestion_id[1:]) for s in history if s.suggestion_id.startswith("s")]
        gs._next_suggestion_id = (max(used_ids) + 1) if used_ids else 1
        return gs

    def _adopt(self, other: "GameState") -> None:
        self.engine = other.engine
        self.history = other.history
        self._initial_hand = other._initial_hand
        self._next_suggestion_id = other._next_suggestion_id

    @property
    def user_owner_id(self) -> str:
        return self.players[self.user_seat].owner_id

    def _apply_initial_hand_facts(self) -> None:
        user_owner = self.user_owner_id
        hand_set = set(self._initial_hand)
        source = FactSource("initial_hand")
        for card in self._initial_hand:
            self.engine.add_owned(card, user_owner, source)
        for card in self.cards:
            if card not in hand_set:
                self.engine.add_not_owned(card, user_owner, source)

    def _apply_suggestion_facts(self, suggestion: Suggestion) -> None:
        source = FactSource("suggestion", suggestion.suggestion_id)
        for response in suggestion.responses:
            responder = seat_id(response.responder_seat)
            if response.outcome == "no_show":
                for card in suggestion.triple:
                    self.engine.add_not_owned(card, responder, source)
            elif response.outcome == "shown_to_me":
                self.engine.add_owned(response.shown_card, responder, source)
            elif response.outcome == "shown_unseen":
                self.engine.add_at_least_one(responder, suggestion.triple, source)

    # -------------------------------------------------------------- mutations

    def set_user_hand(self, cards: list[Card]) -> None:
        candidate = GameState.from_history(self.config, self.players, self.user_seat, cards, self.history)
        self._adopt(candidate)

    def responders_in_order(self, suggester_seat: int) -> list[int]:
        n = len(self.players)
        return [(suggester_seat + i) % n for i in range(1, n)]

    def record_suggestion(
        self,
        suggester_seat: int,
        suspect: Card,
        weapon: Card,
        room: Card,
        responses: list[SuggestionResponse],
    ) -> Suggestion:
        sid = f"s{self._next_suggestion_id}"
        suggestion = Suggestion(sid, suggester_seat, suspect, weapon, room, tuple(responses))
        candidate_history = self.history + [suggestion]
        candidate = GameState.from_history(
            self.config, self.players, self.user_seat, self._initial_hand, candidate_history
        )
        self._adopt(candidate)
        return suggestion

    def undo_last_suggestion(self) -> None:
        if not self.history:
            return
        candidate_history = self.history[:-1]
        candidate = GameState.from_history(
            self.config, self.players, self.user_seat, self._initial_hand, candidate_history
        )
        self._adopt(candidate)

    def delete_suggestion(self, suggestion_id: str) -> None:
        candidate_history = [s for s in self.history if s.suggestion_id != suggestion_id]
        candidate = GameState.from_history(
            self.config, self.players, self.user_seat, self._initial_hand, candidate_history
        )
        self._adopt(candidate)

    def edit_suggestion(
        self,
        suggestion_id: str,
        suggester_seat: int,
        suspect: Card,
        weapon: Card,
        room: Card,
        responses: list[SuggestionResponse],
    ) -> None:
        updated = Suggestion(suggestion_id, suggester_seat, suspect, weapon, room, tuple(responses))
        candidate_history = [updated if s.suggestion_id == suggestion_id else s for s in self.history]
        candidate = GameState.from_history(
            self.config, self.players, self.user_seat, self._initial_hand, candidate_history
        )
        self._adopt(candidate)

    # ----------------------------------------------------------------- reads

    @property
    def last_solver_stats(self) -> SolverStats:
        return self.engine.last_stats

    def detective_sheet(self) -> dict:
        sheet = {}
        for card in self.cards:
            owner = self.engine.owner_of(card)
            if owner is not None:
                sheet[card] = {"status": "confirmed", "owner": owner, "possible": {owner}}
            else:
                sheet[card] = {"status": "ambiguous", "owner": None, "possible": self.engine.possible_owners(card)}
        return sheet

    def explain_card(self, card: Card) -> Optional[Explanation]:
        return self.engine.explanations.explanation_for(card)

    def explain_card_full_chain(self, card: Card) -> list[Explanation]:
        top = self.explain_card(card)
        if top is None:
            return []
        return full_derivation_chain(top, self.engine.explanations)

    def card_probabilities(self, max_ambiguous: int = 14) -> dict:
        """Per-card {owner_id: probability} for every card, confirmed cards
        included trivially as 1.0. Raises TooManyAmbiguousCardsError if not
        enough is known yet to compute this exactly."""
        return full_probabilities(self.engine, max_ambiguous=max_ambiguous)

    def is_solved(self) -> bool:
        return self.engine.is_solved()

    def solution(self):
        return self.engine.solution()

    def best_suggestions(self, top_k: int = 8):
        from cluedo.advisor import rank_candidates  # local import avoids a circular dependency

        return rank_candidates(self, top_k=top_k)

    # -------------------------------------------------------------- save/load

    def to_dict(self) -> dict:
        return {
            "save_format_version": SAVE_FORMAT_VERSION,
            "card_config": {
                "edition": self.config.edition,
                "suspects": list(self.config.suspects),
                "weapons": list(self.config.weapons),
                "rooms": list(self.config.rooms),
            },
            "players": [
                {"name": p.name, "seat_index": p.seat_index, "hand_size": p.hand_size} for p in self.players
            ],
            "user_seat": self.user_seat,
            "initial_hand": [c.name for c in self._initial_hand],
            "history": [_suggestion_to_dict(s) for s in self.history],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        if not isinstance(data, dict) or data.get("save_format_version") != SAVE_FORMAT_VERSION:
            raise SaveFileError("Unrecognized or incompatible save file format.")
        try:
            cfg_data = data["card_config"]
            config = CardConfig(
                edition=cfg_data["edition"],
                suspects=tuple(cfg_data["suspects"]),
                weapons=tuple(cfg_data["weapons"]),
                rooms=tuple(cfg_data["rooms"]),
            )
            cards_by_name = {c.name: c for c in config.all_cards()}
            players = [Player(p["name"], p["seat_index"], p["hand_size"]) for p in data["players"]]
            user_seat = data["user_seat"]
            initial_hand = [cards_by_name[name] for name in data["initial_hand"]]
            history = [_suggestion_from_dict(s, cards_by_name) for s in data["history"]]
        except (KeyError, TypeError) as exc:
            raise SaveFileError(f"Couldn't load this file: malformed data ({exc}).") from exc

        try:
            return cls.from_history(config, players, user_seat, initial_hand, history)
        except ContradictionError as exc:
            raise SaveFileError(f"This save file describes an impossible game state: {exc.message}") from exc


def _suggestion_to_dict(s: Suggestion) -> dict:
    return {
        "suggestion_id": s.suggestion_id,
        "suggester_seat": s.suggester_seat,
        "suspect": s.suspect.name,
        "weapon": s.weapon.name,
        "room": s.room.name,
        "responses": [
            {
                "responder_seat": r.responder_seat,
                "outcome": r.outcome,
                "shown_card": r.shown_card.name if r.shown_card else None,
            }
            for r in s.responses
        ],
    }


def _suggestion_from_dict(d: dict, cards_by_name: dict) -> Suggestion:
    responses = tuple(
        SuggestionResponse(
            r["responder_seat"],
            r["outcome"],
            cards_by_name[r["shown_card"]] if r.get("shown_card") else None,
        )
        for r in d["responses"]
    )
    return Suggestion(
        d["suggestion_id"],
        d["suggester_seat"],
        cards_by_name[d["suspect"]],
        cards_by_name[d["weapon"]],
        cards_by_name[d["room"]],
        responses,
    )


def save_game(game_state: GameState, path: Path | str) -> None:
    """Atomic write (temp file + os.replace) with a rolling .bak backup, so a
    crash mid-write can never corrupt the existing save."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = game_state.to_dict()

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        if path.exists():
            backup_path = path.with_name(path.name + ".bak")
            try:
                if backup_path.exists():
                    backup_path.unlink()
                path.replace(backup_path)
            except OSError:
                pass  # backup is best-effort; never block the actual save

        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def load_game(path: Path | str) -> GameState:
    path = Path(path)
    if not path.exists():
        raise SaveFileError(f"No such file: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise SaveFileError(f"Couldn't load this file: {exc}") from exc
    return GameState.from_dict(data)


def default_autosave_path() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home() / ".cluedo_assistant")
    return base / "CluedoAssistant" / "autosave.json"
