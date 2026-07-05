"""SQLAlchemy ORM models.

Importing this package imports every model module, which is what registers all
mappers on the shared ``Base`` and lets string-based ``relationship()`` targets
resolve. Alembic's ``env.py`` and the test harness import it for exactly that
reason: a model missing from here is invisible to autogenerate.
"""

from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.calibration import CalibrationRun
from pattern_mirror.models.dictionary import Dictionary
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.drift import (
    DriftFinding,
    DriftFindingDismissal,
    DriftFindingInteraction,
)
from pattern_mirror.models.engine import Flag, FlagDismissal
from pattern_mirror.models.growth import DictionaryProposal, PendingDictionaryAddition
from pattern_mirror.models.identity import Subject, User, UserRoleAssignment
from pattern_mirror.models.jd_criteria import JdCriterion
from pattern_mirror.models.peer_corroboration import PeerCorroboration
from pattern_mirror.models.peer_feedback import PeerFeedback
from pattern_mirror.models.promotion_rubric import PromotionRubricCriterion
from pattern_mirror.models.reference import Citation, Region

__all__ = [
    "AgentRun",
    "AnalysisRun",
    "CalibrationRun",
    "Citation",
    "Dictionary",
    "DictionaryProposal",
    "Document",
    "DriftFinding",
    "DriftFindingDismissal",
    "DriftFindingInteraction",
    "Flag",
    "FlagDismissal",
    "JdCriterion",
    "PeerCorroboration",
    "PeerFeedback",
    "PendingDictionaryAddition",
    "PromotionRubricCriterion",
    "Region",
    "Subject",
    "User",
    "UserRoleAssignment",
]
