"""Apply the Contextual Pass's GDOR verdicts to the verified flags, a deterministic Module.

The Contextual Pass rules each keyword flag and tags its own; this Module attaches those
rulings to the dictionary flags — which the append-only candidate channel kept out of the
Pass's reach — and splits off the ones it cleared. Only ``unacceptable`` flags surface;
``acceptable`` (a false positive in context) and ``acceptable_with_justification`` are
logged but suppressed, so the manager sees clear bias only (design spec §12, ADR 0010).
"""

from dataclasses import replace

from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.engine.state import DictionaryVerdict
from pattern_mirror.models.enums import FlagSourceStage, FlagVerdict

_SUPPRESSED_VERDICTS = frozenset(
    {FlagVerdict.acceptable, FlagVerdict.acceptable_with_justification}
)


def apply_verdicts(
    flags: list[CandidateFlag], verdicts: list[DictionaryVerdict]
) -> tuple[list[CandidateFlag], list[CandidateFlag]]:
    """Attach verdicts to dictionary flags and split survivors from the suppressed.

    A dictionary flag inherits the verdict the Contextual Pass returned for its span; an
    unreviewed one keeps ``None`` and surfaces. Contextual flags already carry their own
    verdict. A flag the Pass ruled acceptable or acceptable_with_justification is suppressed,
    a dictionary one carrying the ruling's reasoning so the suppression stays auditable.

    Args:
        flags: The Adjudicator's verified flags, every span carrying resolved offsets.
        verdicts: The Contextual Pass's keyword rulings, keyed by span.

    Returns:
        The survivors (``unacceptable`` or unreviewed) and the suppressed flags.
    """
    by_span = {(verdict.start_offset, verdict.end_offset): verdict for verdict in verdicts}
    survivors: list[CandidateFlag] = []
    suppressed: list[CandidateFlag] = []
    for flag in flags:
        resolved = _resolve(flag, by_span)
        if resolved.verdict in _SUPPRESSED_VERDICTS:
            suppressed.append(resolved)
        else:
            survivors.append(resolved)
    return survivors, suppressed


def _resolve(
    flag: CandidateFlag, by_span: dict[tuple[int, int], DictionaryVerdict]
) -> CandidateFlag:
    if flag.source_stage is not FlagSourceStage.dictionary:
        return flag
    assert flag.start_offset is not None and flag.end_offset is not None
    verdict = by_span.get((flag.start_offset, flag.end_offset))
    if verdict is None:
        return flag
    if verdict.verdict in _SUPPRESSED_VERDICTS:
        return replace(flag, verdict=verdict.verdict, explanation=verdict.reasoning)
    return replace(flag, verdict=verdict.verdict)
