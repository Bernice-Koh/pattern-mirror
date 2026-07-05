"""The calibration job scores the live engine over the gold set without persisting scratch rows."""

from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pattern_mirror.engine.contextual_pass import ContextualFlag, ContextualPassResult
from pattern_mirror.engine.judge import JudgeRubric, JudgeSample
from pattern_mirror.jobs.calibrate import _gold_labels, report_fields, run_calibration
from pattern_mirror.jobs.gold_set import GoldDocument, GoldSet
from pattern_mirror.models.enums import (
    BiasCategory,
    DocType,
    FlagScope,
    FlagSourceStage,
    FlagVerdict,
)
from pattern_mirror.models.identity import User
from pattern_mirror.services.calibration import CalibrationReport, StageMetrics


class _FakeClient:
    def __init__(self, result: Any) -> None:
        self._result = result
        self._completion = SimpleNamespace(usage=SimpleNamespace(input_tokens=10, output_tokens=5))

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        return self._result, self._completion


def test_gold_labels_keep_only_surfacing_labels_normalised() -> None:
    document = GoldDocument.model_validate(
        {
            "title": "t",
            "doc_type": "jd",
            "content": "hire a young rockstar, not a quiet planner",
            "labels": [
                {
                    "raw_span": "young",
                    "category": "age",
                    "source_stage": "dictionary",
                    "should_surface": True,
                },
                {
                    "raw_span": "quiet planner",
                    "category": "age",
                    "source_stage": "contextual",
                    "should_surface": False,
                },
            ],
        }
    )

    labels = _gold_labels(document)

    assert [label.normalised_span for label in labels] == ["young"]
    assert labels[0].source_stage is FlagSourceStage.dictionary


def test_report_fields_flattens_per_stage_metrics() -> None:
    report = CalibrationReport(
        per_stage={
            FlagSourceStage.dictionary: StageMetrics(FlagSourceStage.dictionary, 2, 0, 1),
        },
        agreement=0.5,
        ece=0.1,
        brier=0.2,
        scored_count=3,
    )

    fields = report_fields(report)

    assert fields["agreement"] == 0.5
    assert fields["stages"]["dictionary"]["precision"] == 1.0
    assert fields["stages"]["dictionary"]["recall"] == pytest.approx(2 / 3)


@pytest.mark.db
def test_run_calibration_scores_the_engine_and_leaves_no_scratch_rows(db_session: Session) -> None:
    gold = GoldSet(
        documents=[
            GoldDocument(
                title="cal-test",
                doc_type=DocType.jd,
                content="We want a digital native who is a strong culture fit.",
                labels=GoldDocument.model_validate(
                    {
                        "title": "cal-test",
                        "doc_type": "jd",
                        "content": "We want a digital native who is a strong culture fit.",
                        "labels": [
                            {
                                "raw_span": "digital native",
                                "category": "age",
                                "source_stage": "dictionary",
                                "should_surface": True,
                            },
                            {
                                "raw_span": "culture fit",
                                "category": "race",
                                "source_stage": "contextual",
                                "should_surface": True,
                            },
                        ],
                    }
                ).labels,
            )
        ]
    )
    contextual = _FakeClient(
        ContextualPassResult(
            new_flags=[
                ContextualFlag(
                    raw_span="culture fit",
                    category=BiasCategory.race,
                    scope=FlagScope.role_specific,
                    verdict=FlagVerdict.unacceptable,
                    explanation="Vague 'fit' invites in-group bias.",
                )
            ]
        )
    )
    judge = _FakeClient(
        JudgeSample(
            rubrics=[
                JudgeRubric(
                    flag_id=1,
                    references_characteristic=True,
                    reference_style="coded",
                    gdor_plausible=False,
                    stated_objectively=False,
                    reasoning="clear",
                )
            ]
        )
    )

    report = run_calibration(db_session, gold, contextual_client=contextual, judge_client=judge)

    assert report.per_stage[FlagSourceStage.dictionary].recall == 1.0
    assert report.per_stage[FlagSourceStage.contextual].recall == 1.0
    assert report.agreement == 1.0
    assert report.scored_count == 1
    scratch = db_session.scalar(
        select(func.count()).select_from(User).where(User.external_user_id == "calibration-scratch")
    )
    assert scratch == 0
