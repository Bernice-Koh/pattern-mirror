"""Load and validate the labelled gold set (#23, ADR-0008).

The gold set is the engine's answer key: documents whose every correct flag is hand-labelled with
its span, category, and the stage that should produce it. ``jobs.calibrate`` runs the real engine
over these documents and scores its output against the labels. The fixture is JSON package data, so
it is validated once here into Pydantic models — including that each labelled span is verbatim in
its document, the same guarantee the Adjudicator enforces, so an unfindable label fails at load.
"""

from importlib.resources import files

from pydantic import BaseModel, model_validator

from pattern_mirror.models.enums import BiasCategory, DocType, FlagSourceStage

_GOLD_SET_RESOURCE = "gold_set.json"


class GoldLabel(BaseModel):
    """One known-correct flag: the span the engine should flag, its category, and its stage."""

    raw_span: str
    category: BiasCategory
    source_stage: FlagSourceStage
    should_surface: bool


class GoldDocument(BaseModel):
    """A labelled document: the text the engine analyses and the flags it should produce."""

    title: str
    doc_type: DocType
    content: str
    labels: list[GoldLabel]

    @model_validator(mode="after")
    def _spans_are_verbatim(self) -> "GoldDocument":
        """A labelled span the Adjudicator could never verify is a labelling error, not a miss."""
        missing = [label.raw_span for label in self.labels if label.raw_span not in self.content]
        if missing:
            raise ValueError(f"label span(s) not verbatim in '{self.title}': {missing}")
        return self


class GoldSet(BaseModel):
    """The whole labelled set the calibration run is measured against."""

    documents: list[GoldDocument]


def load_gold_set() -> GoldSet:
    """Read and validate the bundled gold-set JSON into a typed ``GoldSet``."""
    raw = files("pattern_mirror.jobs").joinpath("seed_data", _GOLD_SET_RESOURCE).read_text("utf-8")
    return GoldSet.model_validate_json(raw)
