"""Dismissal suppression: signature lookup, span normalisation, partition, document scoping.

The pure tests cover the §12 three-way lookup and the partition that feeds the graph; the
``db``-marked test proves the loader scopes dismissals to one document.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.fingerprint import compute_sentence_fingerprint
from pattern_mirror.engine.state import SuppressedFlag
from pattern_mirror.engine.suppression import (
    DismissalIndex,
    load_active_dismissals,
    normalised_span_of,
    partition_by_dismissal,
)
from pattern_mirror.models.documents import Document
from pattern_mirror.models.engine import FlagDismissal
from pattern_mirror.models.enums import BiasCategory, DocType, FlagSourceStage
from pattern_mirror.models.identity import User


def _dismissal(rule_id: uuid.UUID | None, normalised_span: str, fingerprint: str) -> FlagDismissal:
    return FlagDismissal(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        rule_id=rule_id,
        normalised_span=normalised_span,
        sentence_fingerprint=fingerprint,
        active=True,
    )


def _flag(
    content: str,
    phrase: str,
    *,
    rule_id: uuid.UUID | None = None,
    lemma_key: str | None = None,
    stage: FlagSourceStage = FlagSourceStage.dictionary,
) -> CandidateFlag:
    start = content.index(phrase)
    return CandidateFlag(
        source_stage=stage,
        category=BiasCategory.gender,
        raw_span=phrase,
        start_offset=start,
        end_offset=start + len(phrase),
        dictionary_entry_id=rule_id,
        lemma_key=lemma_key,
    )


def test_no_dismissal_for_the_span_surfaces() -> None:
    index = DismissalIndex.from_dismissals([])

    resolved = index.resolve(rule_id=None, normalised_span="aggressive", sentence_fingerprint="x")

    assert resolved is None


def test_same_signature_is_suppressed_by_that_dismissal() -> None:
    rule_id = uuid.uuid4()
    dismissal = _dismissal(rule_id, "aggressive", "fp-a")
    index = DismissalIndex.from_dismissals([dismissal])

    resolved = index.resolve(
        rule_id=rule_id, normalised_span="aggressive", sentence_fingerprint="fp-a"
    )

    assert resolved == dismissal.id


def test_a_shifted_fingerprint_surfaces() -> None:
    rule_id = uuid.uuid4()
    index = DismissalIndex.from_dismissals([_dismissal(rule_id, "aggressive", "fp-a")])

    assert (
        index.resolve(rule_id=rule_id, normalised_span="aggressive", sentence_fingerprint="fp-b")
        is None
    )


def test_a_contextual_flag_matches_a_null_rule_dismissal() -> None:
    dismissal = _dismissal(None, "culture fit", "fp-c")
    index = DismissalIndex.from_dismissals([dismissal])

    resolved = index.resolve(
        rule_id=None, normalised_span="culture fit", sentence_fingerprint="fp-c"
    )

    assert resolved == dismissal.id


def test_dictionary_and_contextual_signatures_do_not_collide() -> None:
    rule_id = uuid.uuid4()
    index = DismissalIndex.from_dismissals([_dismissal(rule_id, "aggressive", "fp-a")])

    # Same span and fingerprint but no rule: a contextual flag, a different signature.
    assert (
        index.resolve(rule_id=None, normalised_span="aggressive", sentence_fingerprint="fp-a")
        is None
    )


def test_normalised_span_uses_the_lemma_key_when_present() -> None:
    flag = _flag("We want a digital native.", "digital native", lemma_key="digital native")

    assert normalised_span_of(flag) == "digital native"


def test_normalised_span_of_a_contextual_span_with_no_adjective_keeps_the_full_lemma() -> None:
    # "Culture Fits" has no adjective, so it falls back to the whole lemma key — no regression.
    flag = _flag("We value Culture Fits.", "Culture Fits", stage=FlagSourceStage.contextual)

    assert normalised_span_of(flag) == "culture fit"


def test_contextual_span_reduces_to_its_adjective_lemma() -> None:
    # The coded concept is the adjective; the phrase around it is incidental, so it drops out.
    flag = _flag(
        "He took an aggressive stance.", "an aggressive stance", stage=FlagSourceStage.contextual
    )

    assert normalised_span_of(flag) == "aggressive"


def test_contextual_spans_sharing_an_adjective_share_one_key() -> None:
    # The fragmentation fix: two wordings of one concept must group, or no pattern reaches the
    # significance count. Both reduce to "polished".
    stage = FlagSourceStage.contextual
    one = _flag("A polished communicator.", "polished communicator", stage=stage)
    two = _flag("Her polished delivery stood out.", "polished delivery", stage=stage)

    assert normalised_span_of(one) == normalised_span_of(two) == "polished"


def test_contextual_span_reduces_to_its_first_adjective() -> None:
    # A span with more than one adjective takes the head (first) one, not a join, so it still
    # groups with the bare form.
    flag = _flag(
        "an aggressive, competitive streak",
        "aggressive, competitive streak",
        stage=FlagSourceStage.contextual,
    )

    assert normalised_span_of(flag) == "aggressive"


def test_partition_routes_a_matching_flag_to_suppressed() -> None:
    content = "We want an aggressive leader."
    rule_id = uuid.uuid4()
    flag = _flag(content, "aggressive", rule_id=rule_id, lemma_key="aggressive")
    fingerprint = compute_sentence_fingerprint(content, flag.start_offset, flag.end_offset)
    dismissal = _dismissal(rule_id, "aggressive", fingerprint)
    index = DismissalIndex.from_dismissals([dismissal])

    survivors, suppressed = partition_by_dismissal([flag], content=content, index=index)

    assert survivors == []
    assert suppressed == [SuppressedFlag(flag=flag, dismissal_id=dismissal.id)]


def test_partition_keeps_a_flag_whose_context_shifted() -> None:
    content = "We want an aggressive go-getter."
    rule_id = uuid.uuid4()
    flag = _flag(content, "aggressive", rule_id=rule_id, lemma_key="aggressive")
    # A dismissal for the same span but a different sentence fingerprint.
    index = DismissalIndex.from_dismissals([_dismissal(rule_id, "aggressive", "0" * 64)])

    survivors, suppressed = partition_by_dismissal([flag], content=content, index=index)

    assert survivors == [flag]
    assert suppressed == []


@pytest.mark.db
def test_loads_only_active_dismissals_for_the_document(db_session: Session) -> None:
    user = User(
        external_user_id=f"suppression-{uuid.uuid4()}",
        legal_name="Suppression Manager",
        email=f"{uuid.uuid4()}@example.test",
    )
    db_session.add(user)
    db_session.flush()
    document = Document(owner_id=user.id, doc_type=DocType.jd, content="text")
    other = Document(owner_id=user.id, doc_type=DocType.jd, content="other")
    db_session.add_all([document, other])
    db_session.flush()

    mine = FlagDismissal(
        document_id=document.id,
        rule_id=None,
        normalised_span="aggressive",
        sentence_fingerprint="a",
    )
    inactive = FlagDismissal(
        document_id=document.id,
        rule_id=None,
        normalised_span="mature",
        sentence_fingerprint="b",
        active=False,
    )
    theirs = FlagDismissal(
        document_id=other.id,
        rule_id=None,
        normalised_span="aggressive",
        sentence_fingerprint="a",
    )
    db_session.add_all([mine, inactive, theirs])
    db_session.flush()

    loaded = load_active_dismissals(db_session, document.id)

    assert [dismissal.id for dismissal in loaded] == [mine.id]
