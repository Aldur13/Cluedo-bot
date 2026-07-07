"""Full-game integration tests: play out complete, truthful Cluedo games
against the real GameState API -- including undo, save/load, replay, and
what-if along the way -- and check every solver conclusion against the
hidden deal. Formalizes what used to be an ad hoc root-level diagnostic
script into real, parametrized pytest cases."""
import random
import tempfile
from pathlib import Path

import pytest

from cluedo.config import load_bundled_edition
from cluedo.engine import ContradictionError
from cluedo.game import GameState, load_game, save_game
from cluedo.history import build_replay_snapshots, whatif_game_state
from cluedo.models import ENVELOPE, Player, Suggestion, SuggestionResponse, seat_id
from cluedo.probability import TooManyAmbiguousCardsError


def _deal(rng, cfg, players):
    cards = list(cfg.all_cards())
    rng.shuffle(cards)
    by_type = {}
    for c in cards:
        by_type.setdefault(c.type, []).append(c)

    owner_of = {}
    remaining = []
    for group in by_type.values():
        owner_of[group[0]] = ENVELOPE
        remaining.extend(group[1:])
    rng.shuffle(remaining)

    idx = 0
    hands = {}
    for p in players:
        hands[p.owner_id] = remaining[idx: idx + p.hand_size]
        idx += p.hand_size
        for c in hands[p.owner_id]:
            owner_of[c] = p.owner_id
    return owner_of, hands


def _default_hand_sizes(total, n):
    base, extra = divmod(total, n)
    return [base + (1 if i < extra else 0) for i in range(n)]


def _play_full_game(edition_key, n_players, seed, max_turns=80):
    """Plays one full truthful game and returns a list of bug descriptions
    (empty if everything the solver/advisor/probability engine/replay/save-load/
    undo/what-if did was correct)."""
    bugs = []
    rng = random.Random(seed)
    cfg = load_bundled_edition(edition_key)
    total_non_envelope = len(cfg.suspects) + len(cfg.weapons) + len(cfg.rooms) - 3
    sizes = _default_hand_sizes(total_non_envelope, n_players)
    players = [Player(f"P{i}", i, sizes[i]) for i in range(n_players)]
    owner_of, hands = _deal(rng, cfg, players)

    gs = GameState(cfg, players, user_seat=0)
    gs.set_user_hand(hands["seat_0"])

    all_cards = cfg.all_cards()
    suspects = [c for c in all_cards if c.type.value == "suspect"]
    weapons = [c for c in all_cards if c.type.value == "weapon"]
    rooms = [c for c in all_cards if c.type.value == "room"]

    solved_at = None
    for i in range(max_turns):
        turn = i + 1
        suggester_seat = i % n_players
        suspect = rng.choice(suspects)
        weapon = rng.choice(weapons)
        room = rng.choice(rooms)
        order = gs.responders_in_order(suggester_seat)

        responses = []
        for seat in order:
            owner = seat_id(seat)
            held = [c for c in (suspect, weapon, room) if owner_of.get(c) == owner]
            if held:
                if seat == 0 or suggester_seat == 0:
                    responses.append(SuggestionResponse(seat, "shown_to_me", rng.choice(held)))
                else:
                    responses.append(SuggestionResponse(seat, "shown_unseen"))
                break
            responses.append(SuggestionResponse(seat, "no_show"))

        try:
            gs.record_suggestion(suggester_seat, suspect, weapon, room, responses)
        except ContradictionError as exc:
            bugs.append(f"turn {turn}: engine raised contradiction on a truthful deal: {exc.kind} - {exc.message}")
            return bugs

        sheet = gs.detective_sheet()
        for card, info in sheet.items():
            if info["status"] == "confirmed" and info["owner"] != owner_of[card]:
                bugs.append(
                    f"turn {turn}: WRONG deduction -- {card.name} confirmed to {info['owner']} "
                    f"but true owner is {owner_of[card]}"
                )

        try:
            probs = gs.card_probabilities()
            for card, dist in probs.items():
                total_p = sum(dist.values())
                if abs(total_p - 1.0) > 1e-6:
                    bugs.append(f"turn {turn}: probabilities for {card.name} sum to {total_p}, not 1.0")
                true_owner = owner_of[card]
                if dist.get(true_owner, 0.0) <= 0.0:
                    bugs.append(
                        f"turn {turn}: probability model assigns 0% to the TRUE owner of {card.name} "
                        f"({true_owner}) -- would make it impossible to ever find the real answer"
                    )
        except TooManyAmbiguousCardsError:
            pass
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any other exception is itself the bug
            bugs.append(f"turn {turn}: card_probabilities raised unexpected {type(exc).__name__}: {exc}")

        try:
            candidates = gs.best_suggestions(top_k=5)
            if gs.is_solved() and candidates:
                bugs.append(f"turn {turn}: advisor returned candidates after the game was already solved")
        except Exception as exc:  # noqa: BLE001
            bugs.append(f"turn {turn}: best_suggestions raised unexpected {type(exc).__name__}: {exc}")

        if gs.is_solved():
            suspect_c, weapon_c, room_c = gs.solution()
            if not (owner_of[suspect_c] == ENVELOPE and owner_of[weapon_c] == ENVELOPE and owner_of[room_c] == ENVELOPE):
                bugs.append(f"turn {turn}: solved with WRONG answer {suspect_c.name}/{weapon_c.name}/{room_c.name}")
            else:
                solved_at = turn
            break

    # --- exercise undo/save-load/replay/what-if on the resulting game state ---
    history_before = list(gs.history)
    engine_owner_before = dict(gs.engine.confirmed)

    if gs.history:
        gs.undo_last_suggestion()
        if len(gs.history) != len(history_before) - 1:
            bugs.append("undo_last_suggestion did not remove exactly one entry")
        last = history_before[-1]
        try:
            gs.record_suggestion(last.suggester_seat, last.suspect, last.weapon, last.room, list(last.responses))
        except ContradictionError as exc:
            bugs.append(f"redoing the undone suggestion raised a contradiction: {exc.message}")
        if dict(gs.engine.confirmed) != engine_owner_before:
            bugs.append("state after undo+redo does not match the state before undo")

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "game.json"
        save_game(gs, path)
        loaded = load_game(path)
        if dict(loaded.engine.confirmed) != dict(gs.engine.confirmed):
            bugs.append("save/load round-trip did not preserve confirmed-card state")

    try:
        snapshots = build_replay_snapshots(gs)
        if len(snapshots) != len(gs.history) + 1:
            bugs.append(f"replay snapshot count {len(snapshots)} != history+1 ({len(gs.history) + 1})")
        elif dict(snapshots[-1].game_state.engine.confirmed) != dict(gs.engine.confirmed):
            bugs.append("final replay snapshot does not match live state")
    except Exception as exc:  # noqa: BLE001
        bugs.append(f"build_replay_snapshots raised unexpected {type(exc).__name__}: {exc}")

    if not gs.is_solved() and n_players > 1:
        try:
            hypothetical = Suggestion(
                "__diag_whatif__", 0, suspects[0], weapons[0], rooms[0],
                tuple(SuggestionResponse(s, "no_show") for s in gs.responders_in_order(0)),
            )
            scratch = whatif_game_state(gs, hypothetical)
            if gs.history == scratch.history:
                bugs.append("whatif_game_state scratch history is identical to live history (not applied?)")
        except ContradictionError:
            pass  # the hypothetical was itself contradictory -- expected sometimes, not a bug
        except Exception as exc:  # noqa: BLE001
            bugs.append(f"whatif_game_state raised unexpected {type(exc).__name__}: {exc}")

    return bugs


@pytest.mark.parametrize(
    "edition_key, n_players, seed",
    [
        ("classic_uk", 3, 101),
        ("classic_us", 4, 202),
        ("swedish_2012", 6, 303),
    ],
)
def test_full_truthful_game_has_no_bugs(edition_key, n_players, seed):
    bugs = _play_full_game(edition_key, n_players, seed)
    assert not bugs, "\n".join(bugs)
