"""find_growth_candidates surfaces recurring, uncatalogued, general phrases and nothing else.

Builds contextual ``flags`` against the test database and asserts the trigger's grouping, its two
recurrence axes (distinct managers AND distinct documents), and its two exclusions (already
catalogued, already reviewed). Phrases are synthetic multi-word forms so they never collide with
the seeded SG lexicon.
"""

import pytest
from sqlalchemy.orm import Session

from pattern_mirror.core.config import Settings
from pattern_mirror.engine.fingerprint import compute_sentence_fingerprint
from pattern_mirror.engine.lemmatiser import lemma_key
from pattern_mirror.models.dictionary import Dictionary
from pattern_mirror.models.documents import Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import (
    BiasCategory,
    CitationSourceType,
    DocType,
    FlagScope,
    FlagSourceStage,
)
from pattern_mirror.models.growth import DictionaryProposal
from pattern_mirror.models.identity import User
from pattern_mirror.models.reference import Citation
from pattern_mirror.services.growth_trigger import find_growth_candidates

pytestmark = pytest.mark.db

_PHRASE = "culture add"


def _settings(*, min_managers: int = 1, min_documents: int = 2) -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://unused",
        growth_recurrence_min_managers=min_managers,
        growth_recurrence_min_documents=min_documents,
    )


def _manager(session: Session, n: int) -> User:
    user = User(
        external_user_id=f"mgr-{n}", legal_name=f"Manager {n}", email=f"mgr{n}@example.invalid"
    )
    session.add(user)
    session.flush()
    return user


def _document(session: Session, owner: User, content: str) -> Document:
    document = Document(owner_id=owner.id, doc_type=DocType.jd, content=content)
    session.add(document)
    session.flush()
    return document


def _flag(
    session: Session,
    document: Document,
    phrase: str,
    *,
    scope: FlagScope = FlagScope.general,
    source_stage: FlagSourceStage = FlagSourceStage.contextual,
    with_offsets: bool = True,
) -> Flag:
    start = document.content.index(phrase)
    end = start + len(phrase)
    flag = Flag(
        document_id=document.id,
        source_stage=source_stage,
        category=BiasCategory.gender,
        scope=scope,
        raw_span=phrase,
        normalised_span=lemma_key(phrase),
        sentence_fingerprint=compute_sentence_fingerprint(document.content, start, end),
        start_offset=start if with_offsets else None,
        end_offset=end if with_offsets else None,
        rationale={"explanation": "coded language"},
    )
    session.add(flag)
    session.flush()
    return flag


def _propose_across(
    session: Session,
    phrase: str,
    *,
    managers: int,
    documents_each: int,
    scope: FlagScope = FlagScope.general,
) -> None:
    """Emit ``managers × documents_each`` contextual proposals of ``phrase``, one flag per doc."""
    for m in range(managers):
        manager = _manager(session, m)
        for d in range(documents_each):
            document = _document(session, manager, f"We really value a {phrase} on doc {m}-{d}.")
            _flag(session, document, phrase, scope=scope)


def _catalogue(session: Session, phrase: str) -> None:
    citation = Citation(
        source_type=CitationSourceType.academic, title="Coded language", reference="doi:10.1/x"
    )
    session.add(citation)
    session.flush()
    session.add(
        Dictionary(
            region_code="SG",
            category=BiasCategory.gender,
            term=phrase,
            lemma_key=lemma_key(phrase),
            citation_id=citation.id,
            explanation="already catalogued",
        )
    )
    session.flush()


def test_phrase_recurring_across_managers_and_documents_triggers(db_session: Session) -> None:
    _propose_across(db_session, _PHRASE, managers=3, documents_each=1)

    candidates = find_growth_candidates(db_session, _settings())

    assert len(candidates) == 1
    assert candidates[0].lemma_key == lemma_key(_PHRASE)
    assert candidates[0].phrase == _PHRASE
    assert candidates[0].example_excerpts


def test_a_one_off_proposal_does_not_trigger(db_session: Session) -> None:
    _propose_across(db_session, _PHRASE, managers=1, documents_each=1)

    assert find_growth_candidates(db_session, _settings()) == []


def test_role_specific_phrases_never_trigger(db_session: Session) -> None:
    _propose_across(
        db_session, _PHRASE, managers=3, documents_each=1, scope=FlagScope.role_specific
    )

    assert find_growth_candidates(db_session, _settings()) == []


def test_a_catalogued_phrase_is_excluded(db_session: Session) -> None:
    _propose_across(db_session, _PHRASE, managers=3, documents_each=1)
    _catalogue(db_session, _PHRASE)

    assert find_growth_candidates(db_session, _settings()) == []


def test_an_already_reviewed_phrase_is_excluded(db_session: Session) -> None:
    _propose_across(db_session, _PHRASE, managers=3, documents_each=1)
    db_session.add(DictionaryProposal(phrase=_PHRASE, lemma_key=lemma_key(_PHRASE)))
    db_session.flush()

    assert find_growth_candidates(db_session, _settings()) == []


def test_two_documents_by_one_manager_triggers_by_default(db_session: Session) -> None:
    # The default bar is an occurrence floor, not a cross-manager count: one manager, two docs.
    _propose_across(db_session, _PHRASE, managers=1, documents_each=2)

    candidates = find_growth_candidates(db_session, _settings())

    assert len(candidates) == 1
    assert candidates[0].lemma_key == lemma_key(_PHRASE)


def test_document_floor_is_configurable(db_session: Session) -> None:
    # Two documents no longer clears once the floor is raised to three.
    _propose_across(db_session, _PHRASE, managers=1, documents_each=2)

    assert find_growth_candidates(db_session, _settings(min_documents=3)) == []


def test_manager_floor_is_still_available_as_a_lever(db_session: Session) -> None:
    # Raising the manager bar re-imposes the cross-manager requirement: one manager fails at two.
    _propose_across(db_session, _PHRASE, managers=1, documents_each=2)

    assert find_growth_candidates(db_session, _settings(min_managers=2)) == []


def test_excerpts_are_sentence_windows_capped_at_three(db_session: Session) -> None:
    _propose_across(db_session, _PHRASE, managers=2, documents_each=2)

    candidates = find_growth_candidates(db_session, _settings())

    assert len(candidates) == 1
    excerpts = candidates[0].example_excerpts
    assert len(excerpts) == 3
    assert all(_PHRASE in excerpt and excerpt.endswith(".") for excerpt in excerpts)


def test_excerpts_fall_back_to_the_raw_span_when_offsets_are_absent(db_session: Session) -> None:
    for m in range(3):
        manager = _manager(db_session, m)
        document = _document(db_session, manager, f"We value a {_PHRASE} on doc {m}.")
        _flag(db_session, document, _PHRASE, with_offsets=False)

    candidates = find_growth_candidates(db_session, _settings())

    assert len(candidates) == 1
    assert candidates[0].example_excerpts == [_PHRASE]


def test_representative_phrase_is_the_most_common_surface_form(db_session: Session) -> None:
    manager_a, manager_b, manager_c = (
        _manager(db_session, 0),
        _manager(db_session, 1),
        _manager(db_session, 2),
    )
    for manager, surface in (
        (manager_a, "Culture Add"),
        (manager_b, "Culture Add"),
        (manager_c, _PHRASE),
    ):
        document = _document(db_session, manager, f"We value a {surface} here.")
        _flag(db_session, document, surface)

    candidates = find_growth_candidates(db_session, _settings())

    assert len(candidates) == 1
    assert candidates[0].lemma_key == lemma_key(_PHRASE)
    assert candidates[0].phrase == "Culture Add"
