"""Generate a synthetic resume PDF for a seeded subject (#118).

The MVP resume is a download-only stand-in, so the file only has to be a real, openable PDF —
not a designed CV. We build a minimal single-page PDF by hand rather than pull in a PDF library,
keeping the dependency surface flat (CLAUDE.md: ask before adding a top-level dependency). The
bytes are written to the blob store at seed time and served verbatim by the resume endpoint.
"""

import uuid


def resume_ref(subject_id: uuid.UUID) -> str:
    """The blob reference a subject's resume is stored under."""
    return f"resumes/{subject_id}.pdf"


def _escape(text: str) -> str:
    """Escape the three characters that are special inside a PDF text string literal."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_resume_pdf(*, name: str, subject_type: str) -> bytes:
    """Render a minimal one-page PDF resume for a subject.

    Args:
        name: The subject's name, shown as the heading.
        subject_type: ``candidate`` or ``employee``, shown as the document's framing line.

    Returns:
        A complete, standalone PDF document as bytes.
    """
    lines = [
        name,
        "Synthetic resume - pattern-mirror demo data",
        "",
        f"Profile: interview {subject_type} (synthetic)",
        "Experience: 5 years across platform and delivery teams.",
        "Education: BSc Computer Science.",
        "",
        "This file is placeholder data for the resume download stand-in.",
    ]
    text_ops = "\n".join(f"({_escape(line)}) Tj T*" for line in lines)
    content = f"BT\n/F1 14 Tf\n18 TL\n72 720 Td\n{text_ops}\nET".encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % number + body + b"\nendobj\n"

    xref_offset = len(pdf)
    pdf += b"xref\n0 %d\n" % (len(objects) + 1)
    pdf += b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += b"%010d 00000 n \n" % offset
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1)
    pdf += b"startxref\n%d\n%%%%EOF" % xref_offset
    return bytes(pdf)
