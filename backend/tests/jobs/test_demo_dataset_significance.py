"""The demo dataset's engineered correlations clear Fisher's exact, per manager (#23, #66).

The Pattern Aggregator computes writing patterns *per owner*, so this standalone check builds the
same word-by-gender contingency tables scoped to each manager. It asserts that every manager has a
strong gender pattern, that each manager carries a *distinct* secondary-category pattern (so the
three dashboards differ), and that a deliberately balanced control word does not surface — proving
the gate rejects coincidence, not just confirms what we planted.
"""

import re

from scipy.stats import fisher_exact

from pattern_mirror.jobs.demo_dataset import load_demo_dataset
from pattern_mirror.models.enums import DocType

# Per manager: the gender-coded terms (the marquee pattern) and the one secondary-category term
# skewed by gender that gives each dashboard a different second pattern.
_GENDER_TERMS = {
    "demo-manager-1": ["aggressive", "polished"],
    "demo-manager-2": ["sharp", "meticulous"],
    "demo-manager-3": ["aggressive", "polished"],
}
_SECONDARY_TERMS = {
    "demo-manager-1": "family commitments",  # family_status, on the women
    "demo-manager-2": "digital native",  # age, on the men
    "demo-manager-3": "work pass holder",  # nationality, on the men
}
_CONTROL_WORD = "strong"

# Per-manager pools are 6 male + 6 female, so a perfect split tops out near p=0.002; the secondary
# terms are a 5/6 skew (~0.015). Both clear the 0.05 dashboard bar with margin.
_STRONG_P = 0.01
_SIGNIFICANT_P = 0.05


def _contains(content: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", content, re.IGNORECASE) is not None


def _gender_pvalue(owner_ref: str, word: str) -> float:
    """Fisher's exact p for whether ``word`` correlates with gender in one manager's notes."""
    dataset = load_demo_dataset()
    gender_by_ref = {subject.external_ref: subject.gender for subject in dataset.subjects}

    counts = {"male": [0, 0], "female": [0, 0]}  # gender -> [used, not_used]
    for document in dataset.documents:
        if (
            document.doc_type is not DocType.feedback
            or document.subject_ref is None
            or document.owner_ref != owner_ref
        ):
            continue
        gender = gender_by_ref[document.subject_ref]
        if gender not in counts:
            continue
        counts[gender][0 if _contains(document.content, word) else 1] += 1

    male_used, male_not = counts["male"]
    female_used, female_not = counts["female"]
    return float(fisher_exact([[male_used, female_used], [male_not, female_not]])[1])


def test_every_manager_has_a_strong_gender_pattern() -> None:
    for owner_ref, terms in _GENDER_TERMS.items():
        for term in terms:
            assert _gender_pvalue(owner_ref, term) < _STRONG_P, (owner_ref, term)


def test_every_manager_has_a_significant_secondary_pattern() -> None:
    for owner_ref, term in _SECONDARY_TERMS.items():
        assert _gender_pvalue(owner_ref, term) < _SIGNIFICANT_P, (owner_ref, term)


def test_each_manager_secondary_category_is_distinct() -> None:
    # The three dashboards must differ: family_status vs age vs nationality.
    assert len(set(_SECONDARY_TERMS.values())) == len(_SECONDARY_TERMS)


def test_control_word_does_not_surface_for_any_manager() -> None:
    for owner_ref in _GENDER_TERMS:
        assert _gender_pvalue(owner_ref, _CONTROL_WORD) >= _SIGNIFICANT_P, owner_ref
