"""Fisher's-exact gating: a planted asymmetry clears the bar, a balanced table does not."""

from pattern_mirror.services.significance import Contingency, fisher_p_value, is_significant


def test_strong_asymmetry_is_highly_significant() -> None:
    # All twenty observations split cleanly by group — the planted "all of them were men" pattern.
    table = Contingency(group_a_present=10, group_b_present=0, group_a_absent=0, group_b_absent=10)
    assert fisher_p_value(table) < 0.001


def test_moderate_asymmetry_clears_a_conventional_bar() -> None:
    table = Contingency(group_a_present=5, group_b_present=0, group_a_absent=0, group_b_absent=5)
    assert is_significant(fisher_p_value(table), 0.05)


def test_balanced_table_is_not_significant() -> None:
    table = Contingency(group_a_present=5, group_b_present=5, group_a_absent=5, group_b_absent=5)
    p_value = fisher_p_value(table)
    assert p_value == 1.0
    assert not is_significant(p_value, 0.05)


def test_empty_table_returns_one() -> None:
    assert fisher_p_value(Contingency(0, 0, 0, 0)) == 1.0


def test_total_counts_every_cell() -> None:
    assert Contingency(1, 2, 3, 4).total == 10


def test_is_significant_is_exclusive_at_the_threshold() -> None:
    assert is_significant(0.049, 0.05)
    assert not is_significant(0.05, 0.05)
    assert not is_significant(0.06, 0.05)
