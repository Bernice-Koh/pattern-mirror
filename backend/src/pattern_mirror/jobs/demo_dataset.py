"""Load and validate the synthetic demo dataset (#23).

The dataset is JSON package data, so it crosses a system boundary on the way in and is
validated once here into Pydantic models; the seed job and the significance test then trust
the types. The dataset is *writing-pattern* fixtures: candidate subjects with demographics and
the feedback notes written about them, engineered so that language correlates with gender
strongly enough to clear Fisher's exact in the Pattern Dashboard (#66).
"""

from importlib.resources import files

from pydantic import BaseModel, model_validator

from pattern_mirror.models.enums import DocType, SubjectType

_DATASET_RESOURCE = "demo_dataset.json"


class SubjectSeed(BaseModel):
    """A synthetic person a document is about, with the demographics patterns correlate against."""

    external_ref: str
    legal_name: str
    subject_type: SubjectType
    gender: str | None = None
    age_band: str | None = None


class DocumentSeed(BaseModel):
    """A synthetic JD or feedback note. ``subject_ref`` links feedback to a subject; JDs omit it."""

    title: str
    doc_type: DocType
    role_title: str | None = None
    subject_ref: str | None = None
    content: str


class DemoDataset(BaseModel):
    """The whole dataset: the subjects and the documents written about (or for) them."""

    subjects: list[SubjectSeed]
    documents: list[DocumentSeed]

    @model_validator(mode="after")
    def _refs_resolve(self) -> "DemoDataset":
        """Reject the fixture if refs are inconsistent — a typo must fail at load, not at seed."""
        external_refs = [subject.external_ref for subject in self.subjects]
        unique_refs = set(external_refs)
        if len(external_refs) != len(unique_refs):
            raise ValueError("duplicate subject external_ref in demo dataset")
        unknown = {
            document.subject_ref
            for document in self.documents
            if document.subject_ref is not None and document.subject_ref not in unique_refs
        }
        if unknown:
            raise ValueError(f"document subject_ref(s) with no matching subject: {sorted(unknown)}")
        return self


def load_demo_dataset() -> DemoDataset:
    """Read and validate the bundled demo dataset JSON into a typed ``DemoDataset``."""
    raw = files("pattern_mirror.jobs").joinpath("seed_data", _DATASET_RESOURCE).read_text("utf-8")
    return DemoDataset.model_validate_json(raw)
