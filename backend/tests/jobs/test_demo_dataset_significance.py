"""The demo dataset's engineered language correlations clear Fisher's exact (#23).

This is the standalone significance check that stands in for the not-yet-built Pattern
Aggregator (#66): it builds the same word-by-gender contingency tables the Aggregator will
and asserts the showcase patterns are strongly significant, enough patterns clear the
significance bar to populate the dashboard, and a deliberately balanced control word does
*not* surface — proving the gate rejects coincidence, not just confirms what we planted.
"""

import re

from scipy.stats import fisher_exact

from pattern_mirror.jobs.demo_dataset import load_demo_dataset
from pattern_mirror.models.enums import DocType

# The engineered basket: word -> whether it is a showcase (strong) pattern. The seed content
# places these so each clears the bar below; see the dataset fixture for the exact split.
_SHOWCASE_WORDS = {"sharp", "polished"}
_SIGNIFICANT_WORDS = _SHOWCASE_WORDS | {"aggressive", "collaborative", "cultural fit"}
_CONTROL_WORD = "dependable"

_STRONG_P = 0.001
_SIGNIFICANT_P = 0.05


def _contains(content: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", content, re.IGNORECASE) is not None


def _gender_pvalue(word: str) -> float:
    """Fisher's exact p for whether ``word`` usage is independent of subject gender."""
    dataset = load_demo_dataset()
    gender_by_ref = {subject.external_ref: subject.gender for subject in dataset.subjects}

    counts = {"male": [0, 0], "female": [0, 0]}  # gender -> [used, not_used]
    for document in dataset.documents:
        if document.doc_type is not DocType.feedback or document.subject_ref is None:
            continue
        gender = gender_by_ref[document.subject_ref]
        if gender not in counts:
            continue
        counts[gender][0 if _contains(document.content, word) else 1] += 1

    male_used, male_not = counts["male"]
    female_used, female_not = counts["female"]
    return float(fisher_exact([[male_used, female_used], [male_not, female_not]])[1])


def test_showcase_patterns_are_strongly_significant() -> None:
    for word in _SHOWCASE_WORDS:
        assert _gender_pvalue(word) < _STRONG_P, word


def test_enough_patterns_clear_the_significance_bar() -> None:
    significant = [word for word in _SIGNIFICANT_WORDS if _gender_pvalue(word) < _SIGNIFICANT_P]
    assert len(significant) >= 5, significant


def test_control_word_does_not_surface() -> None:
    assert _gender_pvalue(_CONTROL_WORD) >= _SIGNIFICANT_P
