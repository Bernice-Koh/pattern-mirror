"""load_gold_set validates the fixture and rejects labels whose span is not verbatim."""

import pytest
from pydantic import ValidationError

from pattern_mirror.jobs.gold_set import GoldDocument, load_gold_set
from pattern_mirror.models.enums import FlagSourceStage


def test_loads_documents_with_labels() -> None:
    gold = load_gold_set()

    assert gold.documents
    stages = {label.source_stage for doc in gold.documents for label in doc.labels}
    assert stages == {FlagSourceStage.dictionary, FlagSourceStage.contextual}


def test_includes_a_clean_control_document() -> None:
    gold = load_gold_set()
    assert any(not doc.labels for doc in gold.documents)


def test_rejects_label_span_not_in_content() -> None:
    with pytest.raises(ValidationError, match="not verbatim"):
        GoldDocument.model_validate(
            {
                "title": "bad",
                "doc_type": "jd",
                "content": "a clean sentence",
                "labels": [
                    {
                        "raw_span": "ghost span",
                        "category": "age",
                        "source_stage": "dictionary",
                        "should_surface": True,
                    }
                ],
            }
        )
