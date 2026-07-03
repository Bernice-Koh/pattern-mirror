"""The synthetic resume fixture renders a well-formed PDF and a stable blob ref."""

import uuid

from pattern_mirror.jobs.resume_fixtures import render_resume_pdf, resume_ref


def test_render_returns_a_pdf_document() -> None:
    pdf = render_resume_pdf(name="Ada Lovelace", subject_type="candidate")

    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")


def test_render_xref_offsets_point_at_their_objects() -> None:
    pdf = render_resume_pdf(name="Ada Lovelace", subject_type="candidate")

    start = pdf.rfind(b"startxref")
    xref_offset = int(pdf[start + len(b"startxref") :].split(b"%%EOF")[0].strip())
    rows = pdf[xref_offset:].split(b"\n")
    # rows: 'xref', '0 6', the free entry, then one in-use entry per object.
    for number, row in enumerate(rows[3:8], start=1):
        offset = int(row.split()[0])
        assert pdf[offset:].startswith(b"%d 0 obj" % number)


def test_render_escapes_parentheses_in_the_name() -> None:
    pdf = render_resume_pdf(name="Ada (Lovelace)", subject_type="candidate")

    assert rb"\(Lovelace\)" in pdf


def test_resume_ref_is_the_subjects_pdf_path() -> None:
    subject_id = uuid.uuid4()

    assert resume_ref(subject_id) == f"resumes/{subject_id}.pdf"
