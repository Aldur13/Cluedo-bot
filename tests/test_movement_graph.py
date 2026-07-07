"""MovementGraph tests use small, hand-built synthetic MovementData fixtures
-- never the real (estimated) swedish_2012 numbers -- so correctness here
never depends on distance figures that might later be corrected in the
bundled JSON."""
import pytest

from cluedo.movement.data import MovementData
from cluedo.movement.graph import MovementGraph

ROOMS = ("A", "B", "C", "D")


def _simple_graph(secret_passages=()):
    data = MovementData(
        edition_key="test",
        hub="hub",
        distances_to_hub={"A": 2, "B": 3, "C": 5, "D": 1},
        secret_passages=secret_passages,
    )
    return MovementGraph(data, ROOMS)


def test_hub_only_distance_is_sum_of_both_rooms_hub_distances():
    graph = _simple_graph()
    assert graph.distance("A", "B") == 2 + 3
    assert graph.distance("A", "C") == 2 + 5
    assert graph.distance("B", "D") == 3 + 1


def test_distance_to_self_is_zero():
    graph = _simple_graph()
    assert graph.distance("A", "A") == 0
    route = graph.route("A", "A")
    assert route.path == ("A",)
    assert route.via_secret_passage is False
    assert route.moves_saved is None


def test_distance_is_symmetric_for_every_pair():
    graph = _simple_graph(secret_passages=(("A", "C"),))
    for a in ROOMS:
        for b in ROOMS:
            assert graph.distance(a, b) == graph.distance(b, a)


def test_route_without_passage_goes_through_hub():
    graph = _simple_graph()
    route = graph.route("A", "B")
    assert route.path == ("A", "hub", "B")
    assert route.distance == 5
    assert route.via_secret_passage is False
    assert route.moves_saved is None


def test_secret_passage_shortcut_beats_hub_route():
    # A-C via hub would cost 2+5=7; the passage makes it instant (0), and
    # always reachable regardless of dice.
    graph = _simple_graph(secret_passages=(("A", "C"),))
    route = graph.route("A", "C")
    assert route.distance == 0
    assert route.path == ("A", "C")
    assert route.via_secret_passage is True
    assert route.moves_saved == 7


def test_secret_passage_does_not_shortcut_unrelated_pairs():
    # The passage connects A and C directly; B-D shouldn't be affected by
    # it at all (routing through a passage endpoint mid-route never helps
    # once hub weights are positive -- see graph.py's docstring).
    graph = _simple_graph(secret_passages=(("A", "C"),))
    route = graph.route("B", "D")
    assert route.via_secret_passage is False
    assert route.distance == 3 + 1


def test_two_passages_never_chain_through_the_hub():
    # Regression test for a real bug: with passages A<->C and B<->D, a
    # naive all-edges shortest-path graph finds A -> hub -> B (roll+move,
    # cost 5) -> free passage to D (cost 0) = 5, "shorter" than the direct
    # hub route A-D (2+6=8). That's not a legal single Cluedo turn -- you
    # can't roll dice to reach B and ALSO use a passage the same turn, and
    # B/D aren't A's own passage pair. The correct distance is the plain
    # hub-only route, 8, with no passage discount at all.
    data = MovementData(
        edition_key="test",
        hub="hub",
        distances_to_hub={"A": 2, "B": 3, "C": 5, "D": 6},
        secret_passages=(("A", "C"), ("B", "D")),
    )
    graph = MovementGraph(data, ROOMS)

    route = graph.route("A", "D")
    assert route.distance == 2 + 6
    assert route.via_secret_passage is False
    assert route.path == ("A", "hub", "D")

    # A's own passage (to C) still works normally.
    assert graph.route("A", "C").distance == 0
    assert graph.route("A", "C").via_secret_passage is True


def test_reachable_rooms_filters_and_sorts_by_distance():
    graph = _simple_graph()
    results = graph.reachable_rooms("D", max_distance=4)
    # D's hub distance is 1: D-A=1+2=3, D-B=1+3=4, D-C=1+5=6 (excluded).
    assert [r.destination for r in results] == ["A", "B"]
    assert [r.distance for r in results] == [3, 4]


def test_reachable_rooms_excludes_origin():
    graph = _simple_graph()
    results = graph.reachable_rooms("A", max_distance=100)
    assert "A" not in [r.destination for r in results]
    assert len(results) == len(ROOMS) - 1


def test_unknown_room_raises():
    graph = _simple_graph()
    with pytest.raises(ValueError):
        graph.distance("A", "nope")
    with pytest.raises(ValueError):
        graph.route("nope", "A")
    with pytest.raises(ValueError):
        graph.reachable_rooms("nope", 10)


def test_all_pairs_precompute_is_fast():
    import time

    start = time.monotonic()
    _simple_graph(secret_passages=(("A", "C"), ("B", "D")))
    elapsed_ms = (time.monotonic() - start) * 1000
    assert elapsed_ms < 100


def test_from_edition_returns_none_for_unsupported_edition():
    assert MovementGraph.from_edition("classic_uk", ("A", "B")) is None


def test_from_edition_returns_graph_for_swedish_2012():
    from cluedo.config import load_bundled_edition

    cfg = load_bundled_edition("swedish_2012")
    graph = MovementGraph.from_edition("swedish_2012", cfg.rooms)
    assert graph is not None
    assert set(graph.all_rooms()) == set(cfg.rooms)
    # The two confirmed secret passages should make these pairs instant.
    assert graph.route("Köket", "Garaget").via_secret_passage is True
    assert graph.route("Vardagsrummet", "Sovrummet").via_secret_passage is True
