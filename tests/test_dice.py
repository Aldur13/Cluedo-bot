"""Pure 2d6 probability math -- no board, no game state."""
from cluedo.movement.dice import full_distribution, probability_sum_at_least, reachable_this_turn


def test_distance_7_matches_worked_example():
    # The exact worked example from the v4.6 spec: a room at distance 7
    # should show 58/42/28/17/8/3% for rolls 7+ through 12.
    dp = full_distribution(7)
    assert round(dp.probabilities[7] * 100) == 58
    assert round(dp.probabilities[8] * 100) == 42
    assert round(dp.probabilities[9] * 100) == 28
    assert round(dp.probabilities[10] * 100) == 17
    assert round(dp.probabilities[11] * 100) == 8
    assert round(dp.probabilities[12] * 100) == 3


def test_probability_sum_at_least_boundaries():
    assert probability_sum_at_least(2) == 1.0
    assert probability_sum_at_least(0) == 1.0
    assert probability_sum_at_least(-5) == 1.0
    assert probability_sum_at_least(13) == 0.0
    assert probability_sum_at_least(100) == 0.0


def test_probability_sum_at_least_is_monotonic_non_increasing():
    values = [probability_sum_at_least(n) for n in range(2, 14)]
    assert all(values[i] >= values[i + 1] for i in range(len(values) - 1))


def test_probability_sum_at_least_matches_known_2d6_table():
    # Out of 36 equally likely (die1, die2) outcomes.
    counts = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}
    for n in range(2, 13):
        expected = sum(counts[k] for k in range(n, 13)) / 36
        assert probability_sum_at_least(n) == expected


def test_reachable_this_turn():
    assert reachable_this_turn(0) is True
    assert reachable_this_turn(12) is True
    assert reachable_this_turn(13) is False


def test_full_distribution_covers_2_through_12():
    dp = full_distribution(5)
    assert dp.distance == 5
    assert set(dp.probabilities.keys()) == set(range(2, 13))
