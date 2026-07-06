"""load_demo_dataset validates the bundled fixture and rejects inconsistent references."""

import pytest
from pydantic import ValidationError

from pattern_mirror.jobs.demo_dataset import DemoDataset, load_demo_dataset
from pattern_mirror.models.enums import DocType, SubjectType

# A minimal valid manager the reject-tests reuse so documents get past owner resolution to the
# specific validator each test exercises.
_MANAGER = {
    "external_user_id": "m-1",
    "legal_name": "One",
    "email": "one@example.test",
    "department": "A",
}


def test_loads_a_gender_balanced_candidate_pool() -> None:
    # Writing patterns correlate a coded term against candidate gender, so the pool must be roughly
    # balanced for an asymmetry ("5 of 5 called aggressive are men") to be meaningful.
    dataset = load_demo_dataset()

    genders = [
        subject.gender
        for subject in dataset.subjects
        if subject.subject_type is SubjectType.candidate
    ]
    males = genders.count("male")
    females = genders.count("female")
    assert males > 0 and females > 0
    assert abs(males - females) <= 2


def test_every_document_is_owned_by_a_declared_manager() -> None:
    dataset = load_demo_dataset()

    manager_ids = {manager.external_user_id for manager in dataset.managers}
    assert dataset.managers
    assert all(document.owner_ref in manager_ids for document in dataset.documents)


def test_every_feedback_document_links_to_a_subject() -> None:
    dataset = load_demo_dataset()

    feedback = [doc for doc in dataset.documents if doc.doc_type is DocType.feedback]
    assert feedback
    assert all(doc.subject_ref is not None for doc in feedback)


def test_peer_feedback_targets_employee_subjects() -> None:
    dataset = load_demo_dataset()

    employee_refs = {
        subject.external_ref
        for subject in dataset.subjects
        if subject.subject_type is SubjectType.employee
    }
    assert dataset.peer_feedback
    assert all(peer.subject_ref in employee_refs for peer in dataset.peer_feedback)


def test_every_promotion_document_links_to_an_employee() -> None:
    dataset = load_demo_dataset()

    employee_refs = {
        subject.external_ref
        for subject in dataset.subjects
        if subject.subject_type is SubjectType.employee
    }
    promotion = [doc for doc in dataset.documents if doc.doc_type is DocType.promotion]
    assert promotion
    assert all(doc.subject_ref in employee_refs for doc in promotion)


def test_every_promotion_level_has_a_rubric() -> None:
    dataset = load_demo_dataset()

    rubric_levels = {rubric.level_label for rubric in dataset.promotion_rubrics}
    promotion_levels = {
        doc.role_title
        for doc in dataset.documents
        if doc.doc_type is DocType.promotion and doc.role_title is not None
    }
    assert promotion_levels
    assert promotion_levels <= rubric_levels


def test_peer_corroboration_criteria_match_the_rubric() -> None:
    dataset = load_demo_dataset()

    rubric_by_level = {
        rubric.level_label: set(rubric.criteria) for rubric in dataset.promotion_rubrics
    }
    level_by_employee = {
        doc.subject_ref: doc.role_title
        for doc in dataset.documents
        if doc.doc_type is DocType.promotion
    }
    assert dataset.peer_corroboration
    for entry in dataset.peer_corroboration:
        level = level_by_employee[entry.subject_ref]
        assert entry.criterion in rubric_by_level[level]


def test_rejects_peer_corroboration_pointing_at_a_non_employee() -> None:
    with pytest.raises(ValidationError, match="not an employee subject"):
        DemoDataset.model_validate(
            {
                "subjects": [
                    {"external_ref": "c1", "legal_name": "A", "subject_type": "candidate"}
                ],
                "documents": [],
                "peer_corroboration": [
                    {"subject_ref": "c1", "criterion": "Owns delivery", "corroborated": True}
                ],
            }
        )


def test_rejects_promotion_without_a_rubric_for_its_level() -> None:
    with pytest.raises(ValidationError, match="no rubric"):
        DemoDataset.model_validate(
            {
                "managers": [_MANAGER],
                "subjects": [{"external_ref": "e1", "legal_name": "E", "subject_type": "employee"}],
                "documents": [
                    {
                        "title": "t",
                        "doc_type": "promotion",
                        "owner_ref": "m-1",
                        "role_title": "Director — Nowhere",
                        "subject_ref": "e1",
                        "content": "x",
                    }
                ],
            }
        )


def test_rejects_a_document_owned_by_no_manager() -> None:
    with pytest.raises(ValidationError, match="owner_ref"):
        DemoDataset.model_validate(
            {
                "managers": [_MANAGER],
                "subjects": [
                    {"external_ref": "c1", "legal_name": "A", "subject_type": "candidate"}
                ],
                "documents": [
                    {"title": "t", "doc_type": "jd", "owner_ref": "ghost", "content": "x"}
                ],
            }
        )


def test_rejects_one_manager_owning_two_jds_for_a_role() -> None:
    with pytest.raises(ValidationError, match="two JDs for role"):
        DemoDataset.model_validate(
            {
                "managers": [_MANAGER],
                "subjects": [],
                "documents": [
                    {
                        "title": "A",
                        "doc_type": "jd",
                        "owner_ref": "m-1",
                        "role_title": "Analyst",
                        "content": "x",
                    },
                    {
                        "title": "B",
                        "doc_type": "jd",
                        "owner_ref": "m-1",
                        "role_title": "Analyst",
                        "content": "x",
                    },
                ],
            }
        )


def test_two_managers_may_run_the_same_role() -> None:
    dataset = DemoDataset.model_validate(
        {
            "managers": [
                _MANAGER,
                {
                    "external_user_id": "m-2",
                    "legal_name": "T",
                    "email": "t@example.test",
                    "department": "B",
                },
            ],
            "subjects": [],
            "documents": [
                {
                    "title": "A",
                    "doc_type": "jd",
                    "owner_ref": "m-1",
                    "role_title": "Analyst",
                    "content": "x",
                },
                {
                    "title": "B",
                    "doc_type": "jd",
                    "owner_ref": "m-2",
                    "role_title": "Analyst",
                    "content": "x",
                },
            ],
        }
    )
    assert len(dataset.documents) == 2


def test_rejects_peer_feedback_pointing_at_a_non_employee() -> None:
    with pytest.raises(ValidationError, match="not an employee subject"):
        DemoDataset.model_validate(
            {
                "subjects": [
                    {"external_ref": "c1", "legal_name": "A", "subject_type": "candidate"}
                ],
                "documents": [],
                "peer_feedback": [
                    {
                        "subject_ref": "c1",
                        "author_label": "peer",
                        "strengths": "s",
                        "development": "d",
                        "overall": "o",
                    }
                ],
            }
        )


def test_rejects_duplicate_subject_ref() -> None:
    with pytest.raises(ValidationError, match="duplicate subject external_ref"):
        DemoDataset.model_validate(
            {
                "subjects": [
                    {"external_ref": "s1", "legal_name": "A", "subject_type": "candidate"},
                    {"external_ref": "s1", "legal_name": "B", "subject_type": "candidate"},
                ],
                "documents": [],
            }
        )


def test_rejects_document_pointing_at_unknown_subject() -> None:
    with pytest.raises(ValidationError, match="no matching subject"):
        DemoDataset.model_validate(
            {
                "managers": [_MANAGER],
                "subjects": [
                    {"external_ref": "s1", "legal_name": "A", "subject_type": "candidate"}
                ],
                "documents": [
                    {
                        "title": "t",
                        "doc_type": "feedback",
                        "owner_ref": "m-1",
                        "subject_ref": "ghost",
                        "content": "x",
                    }
                ],
            }
        )
