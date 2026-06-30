"""Fisher's-exact significance gating for the Pattern Aggregator (#66, design spec §6).

Pure statistics over plain counts — no database, no engine — so the gate stays deterministic in
CI. A 2x2 contingency table goes in and a two-sided p-value comes out; only patterns whose p
clears the configured threshold are surfaced, so anything that could be coincidence does not.
"""

from dataclasses import dataclass

from scipy.stats import fisher_exact


@dataclass(frozen=True)
class Contingency:
    """A 2x2 table: an attribute present/absent against a binary group (e.g. term × gender)."""

    group_a_present: int
    group_b_present: int
    group_a_absent: int
    group_b_absent: int

    @property
    def total(self) -> int:
        """Every observation in the table."""
        return (
            self.group_a_present + self.group_b_present + self.group_a_absent + self.group_b_absent
        )


def fisher_p_value(table: Contingency) -> float:
    """Two-sided Fisher's exact p for the table; 1.0 when the table is empty (nothing to test)."""
    if table.total == 0:
        return 1.0
    _, p_value = fisher_exact(
        [
            [table.group_a_present, table.group_b_present],
            [table.group_a_absent, table.group_b_absent],
        ]
    )
    return float(p_value)


def is_significant(p_value: float, threshold: float) -> bool:
    """Whether a p-value clears the gate. Boundary is exclusive: strictly below the threshold."""
    return p_value < threshold
