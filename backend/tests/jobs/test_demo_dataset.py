"""load_demo_dataset validates the bundled fixture and rejects inconsistent references."""

import pytest
from pydantic import ValidationError

from pattern_mirror.jobs.demo_dataset import DemoDataset, load_demo_dataset
from pattern_mirror.models.enums import DocType


def test_loads_a_balanced_subject_pool() -> None:
    dataset = load_demo_dataset()

    genders = [subject.gender for subject in dataset.subjects]
    assert genders.count("male") == 12
    assert genders.count("female") == 12


def test_every_feedback_document_links_to_a_subject() -> None:
    dataset = load_demo_dataset()

    feedback = [doc for doc in dataset.documents if doc.doc_type is DocType.feedback]
    assert feedback
    assert all(doc.subject_ref is not None for doc in feedback)


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
                "subjects": [
                    {"external_ref": "s1", "legal_name": "A", "subject_type": "candidate"}
                ],
                "documents": [
                    {
                        "title": "t",
                        "doc_type": "feedback",
                        "subject_ref": "ghost",
                        "content": "x",
                    }
                ],
            }
        )
