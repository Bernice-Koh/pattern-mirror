# Data model

The entities that carry the product's promises, and how they relate. This page is a
map, not a schema reference — the schema source of truth is the Alembic migration
history (`backend/src/pattern_mirror/db/migrations/`), and most columns mean what
their names say. Only the non-obvious ones are explained here.

A **flag** is one piece of bias language the engine identified in a document — a
flagged phrase, its category, and its evidence. Most of the model hangs off that idea:
who wrote the document, what the engine found in it, and how the manager responded.

## The entities

```mermaid
erDiagram
    User ||--o{ Document : "writes"
    User ||--o{ UserRoleAssignment : "holds"
    User |o--o{ PendingDictionaryAddition : "HR decides"
    Subject ||--o{ Document : "is about"
    Subject ||--o{ PeerFeedback : "has"
    Subject ||--o{ PeerCorroboration : "has"

    Document ||--o{ AnalysisRun : "analysed by"
    Document |o--o{ Document : "feedback references its JD"
    Document ||--o{ JdCriterion : "a JD lists"
    Document ||--o{ Flag : "accumulates"
    Document ||--o{ FlagDismissal : "scopes"
    Document ||--o{ DriftFinding : "accumulates"
    Document ||--o{ DriftFindingDismissal : "scopes"

    AnalysisRun |o--o{ Flag : "produces"
    AnalysisRun |o--o{ DriftFinding : "produces"
    AnalysisRun |o--o{ AgentRun : "audits"

    Flag ||--o{ FlagInteraction : "manager answers"
    Flag }o--o| FlagDismissal : "suppressed by"
    Flag }o--o| Dictionary : "dictionary hit uses"
    Flag }o--o| Citation : "carries"

    DriftFinding ||--o{ DriftFindingInteraction : "manager answers"
    DriftFinding }o--o| DriftFindingDismissal : "suppressed by"

    Region ||--o{ Dictionary : "scopes"
    Citation ||--o{ Dictionary : "backs"
    Dictionary }o--o| DictionaryProposal : "grew from"
    DictionaryProposal |o--o| PendingDictionaryAddition : "gate pass queues"
    DictionaryProposal |o--o| Citation : "found"
    DictionaryProposal |o--o{ AgentRun : "audits growth agents"

    User {
        uuid id PK
        string external_user_id "external id, unique"
        string legal_name
        string email
        bool active
    }
    UserRoleAssignment {
        uuid user_id PK,FK
        enum role PK "manager and/or hr"
    }
    Subject {
        uuid id PK
        enum subject_type "candidate (hiring) or employee (promotion)"
        string gender "pattern-analysis dimension"
        string age_band "pattern-analysis dimension"
        string resume_blob_ref "pointer into blob storage"
    }
    Document {
        uuid id PK
        uuid owner_id FK "the manager who wrote it"
        enum doc_type "jd, feedback, promotion"
        text content "live editor text"
        text submitted_content "frozen at submission"
        uuid reference_jd_id FK "if feedback: the JD it hired against"
        uuid subject_id FK "who it is about, if anyone"
    }
    AnalysisRun {
        uuid id PK
        uuid document_id FK
        enum trigger "typed, paused, recheck"
        string content_hash "which text this run saw"
        enum status
    }
    JdCriterion {
        uuid id PK
        uuid jd_document_id FK
        text text "one stated requirement"
        int position
    }
    Flag {
        uuid id PK
        uuid document_id FK
        uuid analysis_run_id FK
        enum source_stage "dictionary or contextual"
        enum category "the bias dimension"
        text raw_span "verbatim, Adjudicator-verified"
        string normalised_span "lemma key"
        string sentence_fingerprint "context hash"
        jsonb rationale "explanation + provenance"
        numeric judge_confidence "sample agreement, null if ungated"
        bool suppressed "logged, hidden in UI"
        uuid suppressed_by_dismissal_id FK
    }
    FlagDismissal {
        uuid id PK
        uuid document_id FK "document-scoped"
        uuid rule_id FK "null for contextual flags"
        string normalised_span
        string sentence_fingerprint
        bool active "undo or recheck clears"
    }
    FlagInteraction {
        uuid id PK
        uuid flag_id FK
        enum kind "accept, dismiss, undo"
        text accepted_alternative "which rewrite, if accepted"
    }
    DriftFinding {
        uuid id PK
        uuid document_id FK
        enum reference_kind "jd_criteria or peer_feedback"
        text criterion "the reference point checked"
        bool addressed "did the writing cover it"
        text evidence "verbatim quote, or null"
        bool suppressed
    }
    DriftFindingDismissal {
        uuid id PK
        uuid document_id FK
        enum reference_kind
        string normalised_criterion
        bool active
    }
    DriftFindingInteraction {
        uuid id PK
        uuid drift_finding_id FK
        enum kind "dismiss, undo"
    }
    Region {
        string code PK "SG for MVP"
        string name
        bool active
    }
    Dictionary {
        uuid id PK
        string region_code FK
        enum category
        string term
        string lemma_key "the matcher's key"
        uuid citation_id FK "mandatory"
        jsonb recommended_alternatives "curated rewrites"
        bool active
        uuid source_proposal_id FK "if grown, not seeded"
    }
    Citation {
        uuid id PK
        enum source_type "academic, regulatory, guideline"
        text reference "DOI, URL, clause"
        text finding
    }
    DictionaryProposal {
        uuid id PK
        text phrase
        string lemma_key "blocks re-review"
        uuid citation_id FK "what the Citation agent found"
    }
    PendingDictionaryAddition {
        uuid id PK
        uuid proposal_id FK
        enum proposed_category
        enum status "pending, approved, rejected, deferred"
        uuid decided_by FK "the HR decision stamp"
    }
    PeerFeedback {
        uuid id PK
        uuid subject_id FK
        text strengths
        text development
        text overall
    }
    PeerCorroboration {
        uuid id PK
        uuid subject_id FK
        text criterion "a rubric point"
        bool corroborated "do peers evidence it"
    }
    AgentRun {
        uuid id PK
        enum agent_name "which LLM stage"
        string model
        jsonb input
        jsonb output
        numeric cost_usd
    }
```

Two entities sit outside the graph because nothing references them:
`PromotionRubricCriterion` (a level's promotion rubric, keyed by `level_label` rather
than an FK — a drift reference corpus) and `CalibrationRun` (one gold-set measurement:
agreement, ECE, Brier, per-stage precision/recall — the calibration time series).

## Significant columns

| Column | What it is |
|---|---|
| `Document.owner_id` | The manager who wrote the document. Every manager-facing query filters on this, so a manager sees only their own writing — and HR queries never read below the firm-wide aggregate, so no HR user can ever open an individual manager's write-up. This one column is the privacy boundary ([overview](overview.md#the-privacy-boundary)) |
| `Document.content` vs `submitted_content` | `content` is the live editor text, changing on every autosave. `submitted_content` freezes what the manager actually submitted, so the dashboard can ask "did the flagged phrase survive to the final version?" — the difference between a manager who fixed a flag and one who dismissed it but left the words in |
| `Document.reference_jd_id` | Interview feedback points back at the job description it was written against. That JD's stated criteria are what the drift check measures the feedback against, and what groups feedback documents by role |
| `Flag.raw_span` | The exact biased phrase, copied verbatim from the document and verified to appear in it, so a flag can never quote text the manager didn't write |
| `Flag.normalised_span` + `sentence_fingerprint` | A flag's fingerprint — the lemma-reduced phrase and a hash of its sentence. Stored on the flag so that when the manager dismisses it, the dismissal records the exact same fingerprint the flag had, and a later run can tell "same concern, same context" from "the sentence changed" ([flags-and-suppression.md](flags-and-suppression.md)) |
| `Flag.suppressed` + `suppressed_by_dismissal_id` | A suppressed flag is one the manager already dismissed in this document, or that the engine cleared as fine in context — it is hidden from the manager but kept in the database, because the Pattern Dashboard still needs to count that the phrase came up. `suppressed_by_dismissal_id` records which dismissal hid it |
| `Flag.judge_confidence` — `Numeric(4, 3)` | How sure the Judge is the flag is real, as the fraction of its repeated checks that agreed, to three decimals. `NULL` means the flag skipped the Judge entirely (a deterministic dictionary hit, or no LLM configured) — which is different from `0.0`, meaning the Judge checked and unanimously disagreed |
| `AnalysisRun.content_hash` | The hash of the exact document text a run analysed, so a flag's character offsets still point at the right words even after the manager keeps editing |
| `Dictionary.citation_id` (non-nullable) | Every dictionary entry must cite a real source. The column can't be null, so a biased-term entry with no evidence behind it cannot exist in the first place |
| `Dictionary.lemma_key` (unique with region + category) | One entry per normalised term, per jurisdiction, per bias category — so "young", "younger" and "Young!" can't pile up as separate dictionary rows |
| `UserRoleAssignment` (separate table) | One person can be both a manager and an HR reviewer. Roles live in their own table, and the current session's active role — not the user record — decides which portal they're using and what they can see |
| `FlagInteraction` | Every time the manager responds to a flag we showed them — accepting a suggested rewrite, dismissing the flag, or undoing a dismissal — it is recorded here as its own row. Doing nothing writes no row, so "the manager ignored this flag" is simply the absence of any interaction. This log is how the dashboard knows how a manager actually reacts to the bias it surfaces |

## Blob storage

PostgreSQL holds all text — document content is `Text` columns, deliberately not
blobs, because it is short-form and queried constantly. The only binaries are files:
`Subject.resume_blob_ref` and `User.avatar_blob_ref` are string pointers into blob
storage (local disk in dev, Azure Blob in production, one interface). The engine never
reads blobs.
