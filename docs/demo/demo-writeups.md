# Demo content pack — live writeups to type in the UI

These are the showcase documents to **enter by hand during the demo**, on top of the seeded
history. The seeded history (run by the `seed_demo*` jobs) is what powers the Pattern Dashboard and
the HR view; these live entries show the *per-document* flow — flags streaming in as you type, drift
coverage, and the promotion corroboration panel — for a fresh document.

**Sign-in:** the three managers are mock-login users `demo-manager-1` (Alex Tan, Markets),
`demo-manager-2` (Priya Sharma, Technology), `demo-manager-3` (Marcus Wong, Ops & Compliance).
HR is `demo-hr-1` (Jordan Lee).

Each writeup names the **role / subject / level** it belongs to so its links resolve against the
seeded data. Coded language that should flag is called out under each.

---

## Alex Tan (Markets) — gender + family_status

### JD Studio — publish a JD
**Role:** `Markets Analyst` (a JD for this role already exists; publishing a second is fine for the
demo, or use a new role title like `Markets Associate`).

> We're after a young, dynamic go-getter to join our fast-paced equity derivatives desk — someone
> aggressive, hungry to win, able to dedicate 70 hours a week with weekends expected. Recent
> graduates with the right energy encouraged to apply.

**Should flag:** `young`, `dynamic` (age), `aggressive` (gender), `recent graduate` (age), and the
**70 hours / weekends expected** availability demand (family-status / caregiver exclusion). On
**Publish**, review the AI-drafted criteria and confirm them.

### Feedback Checkpoint — interview feedback
**Role:** `Markets Analyst` · **Candidate:** any female candidate (e.g. a new "Olivia Tan").

> Olivia is a polished, collaborative candidate who presented her analysis really well. Warm and a
> genuine team player. She did mention some family commitments, so I'm not sure she'd manage the
> desk hours.

**Should flag:** `polished`, `collaborative`, `warm` (gender, contextual), `family commitments`
(family_status). **Drift:** the note addresses none of the JD's technical criteria (Python,
derivatives pricing, risk) — the coverage panel should show them unaddressed.

### Promotion Writeup — evaluate for promotion
**Level:** `Director — Markets` · **Employee:** Nadia Farouk (seeded, has peer feedback + rubric).

> Nadia is a lovely, supportive presence on the desk — always willing to help, keeps everyone's
> spirits up, and is nurturing with the juniors. She's well-liked and dependable. I'm putting her
> forward for Director because she works so hard to keep the team happy.

**Should flag:** `supportive`, `nurturing`, `dependable` (gender-coded). **Rubric coverage:** the
writeup evidences none of *owns P&L / drives strategy / risk calls / develops traders*, yet the
**"what peers say"** panel shows peers corroborate all four — the writeup-vs-corroboration gap.

### Seeded promotion showcases (open these — no typing needed)
Alex has three seeded, submitted promotion writeups whose **peer-corroboration panels are static**
(they render without an LLM call), so they demo even before priming:

- **Nadia Farouk → Director** — *gendered under-selling.* Writeup praises warmth/support; peers
  corroborate all four technical criteria the writeup omits. (Peers supply what the writeup didn't.)
- **Victor Salleh → Director** — *personal bias.* Writeup over-advocates ("we have lunch most
  weekends, he's like family to me"), yet peers **do not** corroborate *drives strategy* or
  *develops traders*. The manager's closeness, not the evidence, is carrying the case.
- **Kavya Menon → Vice President** — *fair, fact-based counter.* A recent joiner: peers say she's
  "inexperienced" and corroborate almost nothing, but the writeup counters with first-hand evidence
  ("I interviewed her and reviewed her work; she rebuilt the risk report and made the delta call
  before CPI"). The contrast with Victor is the point — thin corroboration is not always bias.

---

## Priya Sharma (Technology) — age + gender

### JD Studio — publish a JD
**Role:** `Software Engineer` (or a new `Frontend Engineer`).

> Looking for a young, high-energy digital native to join our fast-moving squad — someone who lives
> and breathes the latest frameworks. Recent grads welcome; we move fast and love a rockstar.

**Should flag:** `young`, `digital native`, `recent grad` (age). Confirm criteria on publish.

### Feedback Checkpoint — interview feedback
**Role:** `Software Engineer` · **Candidate:** a young male candidate (e.g. "Ben Lim").

> Ben is a sharp engineer and a real digital native — picked up the stack in a day. Assertive in
> design reviews and a young, hungry developer. Strong hire.

**Should flag:** `sharp`, `assertive` (gender), `digital native`, `young` (age). Drift: technical JD
criteria mostly unaddressed.

### Promotion Writeup
**Level:** `Director — Engineering` · **Employee:** Farah Idris (seeded).

> Farah is a lovely, supportive teammate who keeps the squad happy and organises our socials. She's
> nurturing with new joiners and everyone likes working with her. Recommending her for Director
> because she's so dependable.

**Should flag:** `supportive`, `nurturing`, `dependable`. Coverage gap vs the technical rubric, with
peers corroborating her delivery.

---

## Marcus Wong (Operations & Compliance) — race + nationality

### JD Studio — publish a JD
**Role:** `Operations Analyst` (or new `Settlements Officer`).

> Fast-paced settlements role in a young, dynamic team. Must be comfortable in a Chinese-speaking
> environment. Singaporeans preferred; work pass holders need not apply.

**Should flag:** `young`, `dynamic` (age), `Chinese-speaking environment` (race), `work pass holder`
(nationality). Confirm criteria on publish.

### Feedback Checkpoint — interview feedback
**Role:** `Operations Analyst` · **Candidate:** a male candidate (e.g. "Imran Shah").

> Imran is decisive and process-driven, and assertive in escalating breaks. He's a work pass holder,
> currently on an EP, so we'd need to sponsor him — timing to check. Capable operator.

**Should flag:** `decisive`, `assertive` (gender), `work pass holder` (nationality). Drift vs the ops
JD criteria.

### Promotion Writeup
**Level:** `Head — Operations` · **Employee:** Aisha Karim (seeded).

> Aisha is a warm, supportive team lead everyone likes. She keeps the desk calm, helps whenever
> asked, and is nurturing with new joiners. Putting her forward for Head of Ops because she's so
> well-liked and keeps morale high.

**Should flag:** `warm`, `supportive`, `nurturing`. Coverage gap vs the operational rubric, peers
corroborating her process ownership.

---

## Notes

- The seeded promotion writeups are **submitted history** (so the dashboard and reopened coverage
  work); the ones above are **new drafts** you create live, which run the engine as you submit.
- Every coded term above is either a dictionary hit (deterministic, instant) or a contextual hit
  (streams in after a short pause). Gender adjectives are contextual; age/race/nationality/family
  terms are dictionary.

### Priming the dashboard (requires Anthropic credits)
`seed_demo` seeds the documents, subjects, peer feedback, rubrics, and corroboration — the static
panels (peer corroboration) work immediately. The **Pattern Dashboard** and the **contextual
(gender) flags** need the LLM pipeline, so run, from `backend/` with a funded `ANTHROPIC_API_KEY`:

```
python -m pattern_mirror.jobs.seed_demo_analysis    # flags + drift over the submitted history
python -m pattern_mirror.jobs.seed_demo_behaviour   # accept/dismiss interactions -> decision patterns
```

`seed_demo_analysis` now **retries any document whose earlier priming failed** (e.g. a spent credit
balance), so it is safe to re-run — it completes only what is missing. A dictionary-only run (no
key) populates the deterministic age/family/nationality flags but not the gender marquee.
