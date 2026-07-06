"""Randomized property tests: deal a real (hidden) solution, generate truthful
suggestions/responses from it, and assert the solver is never wrong -- every
confirmed card matches the ground-truth deal, and a claimed solution is
always the real one. Uses a seeded RNG so runs are reproducible."""
import random

import pytest

from cluedo.config import load_bundled_edition
from cluedo.engine import ContradictionError
from cluedo.game import GameState
from cluedo.models import ENVELOPE, Player, SuggestionResponse, seat_id


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
        hands[p.owner_id] = remaining[idx : idx + p.hand_size]
        idx += p.hand_size
        for c in hands[p.owner_id]:
            owner_of[c] = p.owner_id
    return owner_of, hands


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_random_truthful_game_never_produces_wrong_deduction(seed):
    rng = random.Random(seed)
    cfg = load_bundled_edition("classic_uk")
    players = [Player("P0", 0, 6), Player("P1", 1, 6), Player("P2", 2, 6)]
    owner_of, hands = _deal(rng, cfg, players)

    gs = GameState(cfg, players, user_seat=0)
    gs.set_user_hand(hands["seat_0"])

    all_cards = cfg.all_cards()
    suspects = [c for c in all_cards if c.type.value == "suspect"]
    weapons = [c for c in all_cards if c.type.value == "weapon"]
    rooms = [c for c in all_cards if c.type.value == "room"]

    for _ in range(20):
        suspect = rng.choice(suspects)
        weapon = rng.choice(weapons)
        room = rng.choice(rooms)
        suggester_seat = rng.choice([0, 1, 2])
        responder_order = gs.responders_in_order(suggester_seat)

        responses = []
        for seat in responder_order:
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
        except ContradictionError:
            pytest.fail("engine raised a contradiction against a truthful deal -- solver is unsound")

        sheet = gs.detective_sheet()
        for card, info in sheet.items():
            if info["status"] == "confirmed":
                assert info["owner"] == owner_of[card], (
                    f"engine wrongly confirmed {card.name} to {info['owner']}, "
                    f"but the true owner is {owner_of[card]}"
                )

        if gs.is_solved():
            suspect_c, weapon_c, room_c = gs.solution()
            assert owner_of[suspect_c] == ENVELOPE
            assert owner_of[weapon_c] == ENVELOPE
            assert owner_of[room_c] == ENVELOPE
