"""movement/scoring.py tests: synthetic GameState (via the shared cfg/
cards_by_name/three_players fixtures, classic_uk) + a hand-built tiny
MovementGraph -- never the real swedish_2012 estimates -- so ranking-order
correctness never depends on numbers that might later be corrected."""
from cluedo.game import GameState
from cluedo.movement.data import MovementData
from cluedo.movement.graph import MovementGraph
from cluedo.movement.scoring import rank_rooms

ROOMS = ("Kitchen", "Ballroom", "Conservatory", "Dining Room", "Billiard Room", "Library", "Lounge", "Hall", "Study")


def _fresh_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def _synthetic_graph(secret_passages=(("Kitchen", "Study"),)):
    data = MovementData(
        edition_key="classic_uk",
        hub="hallway_core",
        distances_to_hub={
            "Kitchen": 4, "Ballroom": 3, "Conservatory": 5, "Dining Room": 2, "Billiard Room": 6,
            "Library": 3, "Lounge": 4, "Hall": 2, "Study": 5,
        },
        secret_passages=secret_passages,
    )
    return MovementGraph(data, ROOMS)


def test_no_graph_gives_unsupported_reason(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.set_current_room("Kitchen")
    recommendation = rank_rooms(gs, None)
    assert recommendation.unsupported_reason == "No movement data for this edition yet."
    assert recommendation.rankings == ()
    assert recommendation.best is None


def test_no_current_room_gives_unsupported_reason(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    graph = _synthetic_graph()
    recommendation = rank_rooms(gs, graph)
    assert recommendation.unsupported_reason == "Set your current position to see movement recommendations."
    assert recommendation.rankings == ()


def test_rankings_cover_every_room_and_sort_by_overall_score_desc(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.set_current_room("Hall")
    graph = _synthetic_graph()

    recommendation = rank_rooms(gs, graph)
    assert recommendation.unsupported_reason is None
    assert {r.room for r in recommendation.rankings} == set(ROOMS)

    scores = [r.overall_score for r in recommendation.rankings]
    assert scores == sorted(scores, reverse=True)
    assert recommendation.best == recommendation.rankings[0]


def test_secret_passage_room_is_always_reachable_this_turn(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.set_current_room("Kitchen")
    graph = _synthetic_graph(secret_passages=(("Kitchen", "Study"),))

    recommendation = rank_rooms(gs, graph)
    study_ranking = next(r for r in recommendation.rankings if r.room == "Study")
    assert study_ranking.reach_probability == 1.0
    assert study_ranking.reachable_this_turn is True
    assert study_ranking.distance == 0


def test_room_with_no_advisor_data_still_ranks_with_zero_contribution(cfg, cards_by_name, three_players, monkeypatch):
    import cluedo.movement.scoring as scoring_module

    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.set_current_room("Hall")
    graph = _synthetic_graph()

    monkeypatch.setattr(scoring_module, "_info_gain_by_room", lambda game_state: {})

    recommendation = rank_rooms(gs, graph)
    assert len(recommendation.rankings) == len(ROOMS)
    for ranking in recommendation.rankings:
        assert ranking.expected_info_gain is None
        assert ranking.overall_score == 0.0


def test_secret_passage_rationale_mentions_passage_not_already_here(cfg, cards_by_name, three_players):
    # Regression: _rationale() checked `distance == 0` before `via_secret_passage`,
    # but passage routes always have distance 0 (graph.py's RouteResult), so the
    # passage branch was unreachable dead code -- every passage-reachable room
    # showed the (false) "You're already here." text instead of the passage note.
    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.set_current_room("Kitchen")
    graph = _synthetic_graph(secret_passages=(("Kitchen", "Study"),))

    recommendation = rank_rooms(gs, graph)
    study_ranking = next(r for r in recommendation.rankings if r.room == "Study")
    assert "secret passage" in study_ranking.rationale
    assert "already here" not in study_ranking.rationale


def test_current_room_itself_has_zero_distance_and_full_reach(cfg, cards_by_name, three_players):
    gs = _fresh_game(cfg, cards_by_name, three_players)
    gs.set_current_room("Hall")
    graph = _synthetic_graph()

    recommendation = rank_rooms(gs, graph)
    here = next(r for r in recommendation.rankings if r.room == "Hall")
    assert here.distance == 0
    assert here.reach_probability == 1.0
    assert here.reachable_this_turn is True
    assert "already here" in here.rationale
