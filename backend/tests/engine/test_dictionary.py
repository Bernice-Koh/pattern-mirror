"""Stage-1 dictionary matching: inflection collapse, spans, scoping, no LLM.

The pure-matcher tests build in-memory rules so they run offline; the ``db``-marked
tests exercise ``load_active_rules`` (region and active scoping) against the migrated
seed. Rule ``lemma_key``s are derived through the live lemmatiser, exactly as the seed
builds them, so the tests cannot drift from how terms are actually keyed.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.engine.dictionary import (
    DictionaryRule,
    load_active_rules,
    load_category_citations,
    match_dictionary,
)
from pattern_mirror.engine.lemmatiser import lemma_key
from pattern_mirror.models.dictionary import Dictionary
from pattern_mirror.models.enums import BiasCategory, FlagSourceStage
from pattern_mirror.models.reference import Citation


def _rule(term: str, *, category: BiasCategory = BiasCategory.gender) -> DictionaryRule:
    """A rule keyed exactly as the seed would key ``term``, with synthetic ids."""
    return DictionaryRule(
        id=uuid.uuid4(),
        lemma_key=lemma_key(term),
        category=category,
        citation_id=uuid.uuid4(),
        explanation=f"Synthetic rule for {term!r}.",
        recommended_alternatives=(),
    )


def test_inflected_and_cased_forms_match_the_same_rule() -> None:
    rule = _rule("aggressive", category=BiasCategory.gender)

    lower = match_dictionary("She is aggressive in meetings.", [rule])
    shouted = match_dictionary("Aggressive!", [rule])

    assert len(lower) == len(shouted) == 1
    assert lower[0].dictionary_entry_id == rule.id == shouted[0].dictionary_entry_id


def test_a_flag_carries_offsets_category_and_citation() -> None:
    rule = _rule("aggressive", category=BiasCategory.gender)

    flag = match_dictionary("She is aggressive.", [rule])[0]

    assert flag.source_stage is FlagSourceStage.dictionary
    assert flag.category is BiasCategory.gender
    assert flag.citation_id == rule.citation_id
    assert flag.raw_span == "aggressive"
    assert flag.start_offset is not None and flag.end_offset is not None


def test_clean_text_produces_no_flags() -> None:
    rules = [_rule("aggressive"), _rule("digital native", category=BiasCategory.age)]

    assert match_dictionary("We value clear communication and teamwork.", rules) == []


def test_no_rules_produces_no_flags() -> None:
    assert match_dictionary("Anything at all, even aggressive.", []) == []


def test_matching_makes_no_anthropic_call(monkeypatch: pytest.MonkeyPatch) -> None:
    anthropic = pytest.importorskip("anthropic")

    def _forbid(*args: object, **kwargs: object) -> None:
        raise AssertionError("Stage 1 must not call the LLM")

    monkeypatch.setattr(anthropic.Anthropic, "__init__", _forbid, raising=False)
    rules = [_rule("digital native", category=BiasCategory.age)]

    flags = match_dictionary("We seek a digital native.", rules)

    assert len(flags) == 1


def test_five_hundred_word_document_is_matched() -> None:
    filler = "We value clarity and teamwork across the whole organisation every day. " * 60
    text = f"{filler}We seek a digital native."
    assert len(text.split()) > 500
    rules = [_rule("digital native", category=BiasCategory.age)]

    flags = match_dictionary(text, rules)

    assert len(flags) == 1
    assert flags[0].raw_span == "digital native"


def test_raw_span_is_verbatim_at_its_offsets() -> None:
    text = "We seek a digital native."
    rule = _rule("digital native", category=BiasCategory.age)

    flag = match_dictionary(text, [rule])[0]

    assert text[flag.start_offset : flag.end_offset] == flag.raw_span
    assert flag.raw_span in text


def test_repeated_span_resolves_to_each_position() -> None:
    text = "A bachelor seeks a bachelor."
    rule = _rule("bachelor", category=BiasCategory.family_status)

    flags = match_dictionary(text, [rule])

    assert len(flags) == 2
    offsets = [(flag.start_offset, flag.end_offset) for flag in flags]
    assert offsets[0] != offsets[1]
    assert all(text[start:end] == "bachelor" for start, end in offsets)


def test_multiword_phrase_spans_all_its_words() -> None:
    rule = _rule("digital native", category=BiasCategory.age)

    flag = match_dictionary("They prefer digital natives here.", [rule])[0]

    assert flag.raw_span == "digital natives"


def test_hyphenated_form_matches_across_internal_punctuation() -> None:
    text = "Only non-singaporean staff need apply."
    rule = _rule("non-singaporean", category=BiasCategory.nationality)

    flag = match_dictionary(text, [rule])[0]

    assert flag.raw_span == "non-singaporean"
    assert text[flag.start_offset : flag.end_offset] == "non-singaporean"


def test_longest_match_wins_for_overlapping_rules() -> None:
    short = _rule("young", category=BiasCategory.age)
    phrase = _rule("young professional", category=BiasCategory.age)

    flags = match_dictionary("We want a young professional.", [short, phrase])

    assert len(flags) == 1
    assert flags[0].raw_span == "young professional"
    assert flags[0].dictionary_entry_id == phrase.id


def test_shorter_rule_still_matches_outside_the_phrase() -> None:
    short = _rule("young", category=BiasCategory.age)
    phrase = _rule("young professional", category=BiasCategory.age)

    flags = match_dictionary("We want someone young.", [short, phrase])

    assert len(flags) == 1
    assert flags[0].raw_span == "young"
    assert flags[0].dictionary_entry_id == short.id


def test_one_lemma_key_under_two_categories_yields_one_flag_each() -> None:
    as_age = _rule("mature", category=BiasCategory.age)
    as_gender = _rule("mature", category=BiasCategory.gender)

    flags = match_dictionary("We prefer a mature candidate.", [as_age, as_gender])

    assert len(flags) == 2
    assert {flag.category for flag in flags} == {BiasCategory.age, BiasCategory.gender}
    assert {flag.dictionary_entry_id for flag in flags} == {as_age.id, as_gender.id}
    spans = {(flag.start_offset, flag.end_offset) for flag in flags}
    assert len(spans) == 1


@pytest.mark.db
def test_load_active_rules_returns_the_seeded_sg_lexicon(db_session: Session) -> None:
    rules = load_active_rules(db_session, "SG")

    assert rules
    assert all(isinstance(rule.id, uuid.UUID) for rule in rules)


@pytest.mark.db
def test_load_active_rules_excludes_other_regions(db_session: Session) -> None:
    citation_id = db_session.scalars(select(Citation.id)).first()
    assert citation_id is not None
    db_session.add(
        Dictionary(
            region_code="MY",
            category=BiasCategory.age,
            term="region probe",
            lemma_key="region probe",
            citation_id=citation_id,
            explanation="A Malaysia-scoped entry used only to prove region filtering.",
        )
    )
    db_session.flush()

    sg_ids = {rule.id for rule in load_active_rules(db_session, "SG")}
    my_rules = load_active_rules(db_session, "MY")

    assert len(my_rules) == 1
    assert my_rules[0].id not in sg_ids


@pytest.mark.db
def test_load_active_rules_excludes_inactive_entries(db_session: Session) -> None:
    before = load_active_rules(db_session, "SG")
    deactivated = db_session.scalars(
        select(Dictionary).where(Dictionary.region_code == "SG").limit(1)
    ).one()
    deactivated.active = False
    db_session.flush()

    after = load_active_rules(db_session, "SG")

    assert len(after) == len(before) - 1
    assert deactivated.id not in {rule.id for rule in after}


@pytest.mark.db
def test_load_category_citations_covers_the_seeded_categories(db_session: Session) -> None:
    floor = load_category_citations(db_session, "SG")

    # Every category present in the active SG lexicon has a floor citation (ADR 0006).
    seeded = {rule.category for rule in load_active_rules(db_session, "SG")}
    assert seeded
    assert set(floor) == seeded
    assert all(isinstance(citation_id, uuid.UUID) for citation_id in floor.values())


@pytest.mark.db
def test_seeded_sg_dictionary_flags_a_known_phrase(db_session: Session) -> None:
    rules = load_active_rules(db_session, "SG")

    flags = match_dictionary("We want a digital native for this role.", rules)

    assert len(flags) == 1
    assert flags[0].category is BiasCategory.age
    assert flags[0].raw_span == "digital native"
