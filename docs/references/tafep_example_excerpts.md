# Bias Detection in HR Documents

## 1. The Basics

### What We're Building

An LLM module that scans HR documents (job descriptions, interview feedback, promotion write-ups) and flags biased language. It runs inside a Singapore HR platform.

### The Legal Framework

Singapore's TAFEP (Tripartite Alliance for Fair and Progressive Employment Practices) prohibits discrimination based on these **protected characteristics**:

| Characteristic | Example of Bias |
|---------------|-----------------|
| Age | "Young and energetic", "mature and seasoned", "digital native" |
| Gender | "Masculine leader", "too emotional" (describing a woman) |
| Race | "Must be Chinese", "Chinese-speaking environment" |
| Religion | "Prayer breaks disrupt work" |
| Marital status | "Work like a bachelor", "newly married so might leave" |
| Family responsibility | "No family commitments", pregnancy-based assumptions |
| Disability | Physical assumptions beyond objective job requirements |

### The Only Exception: GDOR

A requirement is lawful **only** if it is a **Genuine and Determining Occupational Requirement** — the job literally cannot function without it. This is a narrow defence.

| ✅ GDOR (Acceptable) | ❌ Not a GDOR (Unacceptable) |
|----------------------|------------------------------|
| "Must be able to lift 15 kg" | "Must be male" |
| "Physically fit to patrol on foot" (security) | "Young and energetic" |
| "Able to work unpredictable hours" | "Work like a bachelor" |

### How Our Model Works

> **Text in → Spot protected characteristics → GDOR check → Flag or pass**

The model flags content for **human review**. It does not make final decisions.

---

## 2. The Decision Rule

```
Does the text reference a protected characteristic?
    │
    ├── NO → ✅ acceptable
    │
    └── YES → Is it a GDOR?
              │
              ├── YES, stated objectively with outcomes → ✅ acceptable_with_justification
              │
              └── NO → ❌ unacceptable
```

**Three verdicts:**
- **`acceptable`** — No bias detected. No protected characteristic referenced.
- **`acceptable_with_justification`** — References a protected characteristic but it's a genuine job requirement. Flag for review only.
- **`unacceptable`** — Contains discriminatory language. Block and alert.

---

## 3. Training Examples

### 3A. Job Descriptions

#### Acceptable

| ID | Text | Verdict | Reasoning |
|----|------|---------|-----------|
| JD-OK1 | "We are looking for candidates who are highly driven and able to thrive in a fast-paced, high-pressure environment with unpredictable hours." | ✅ | States job demands objectively. No protected characteristics referenced. |
| JD-OK2 | "The role requires physical ability to stand for extended periods and lift bundles weighing up to 15 kg." | ✅ w/ justification | Physical requirement is a genuine GDOR. Stated as an objective capability, not an identity trait. |
| JD-OK3 | "We want someone passionate about coding who shows eagerness to learn new languages and frameworks." | ✅ | Describes learning mindset objectively. No protected characteristics. |
| JD-OK4 | "The ideal candidate is naturally cautious, detail-oriented, and sceptical of unchecked optimism." | ✅ | Describes professional temperament for risk management. Not age or personality proxies. |
| JD-OK5 | "Must be physically fit and able to patrol large premises on foot. Must be assertive and capable of handling confrontations calmly." | ✅ w/ justification | Genuine GDOR for security role. Stated as observable behaviours. |

#### Unacceptable

| ID | Text | Verdict | Bias | Reasoning |
|----|------|---------|------|-----------|
| JD-NO1 | "We want young, energetic individuals who can work like a bachelor. Only candidates in their 20s." | ❌ | Age, Marital Status, Family Responsibility | Explicit age limit and marital status proxy. TAFEP prohibits both. Long hours can be stated without referencing protected characteristics. |
| JD-NO2 | "Only male applicants as the job involves heavy lifting." | ❌ | Gender | Gender exclusion is not a GDOR. State physical requirements objectively instead. |
| JD-NO3 | "We want digital natives. Recent university graduates only — older workers will struggle." | ❌ | Age | "Digital native" and "recent graduates only" are age proxies. Skills can be learned at any age. |
| JD-NO4 | "Seeking a mature, seasoned professional. Fresh graduates need not apply." | ❌ | Age | Age-based exclusion against younger workers. Experience must be stated in years, not age proxies. |
| JD-NO5 | "Must be Chinese to communicate with our mostly Chinese tenants. Preferably ex-police, male." | ❌ | Race, Gender | Race is never a hiring requirement. If language proficiency is needed, state the language requirement objectively. |

---

### 3B. Interview Feedback

#### Acceptable

| ID | Text | Verdict | Reasoning |
|----|------|---------|-----------|
| IF-OK1 | "Candidate displayed a hungry, competitive nature and seemed unfazed when probed on handling 90-hour work weeks." | ✅ | Describes demonstrated work drive. Assessment based on responses to scenario probes, not identity. |
| IF-OK2 | "Candidate demonstrated good physical stamina during the practical test, moving boxes without difficulty." | ✅ | Assessment based on observed performance in a practical test. No assumptions about capability based on identity. |
| IF-OK3 | "Jason's enthusiasm and fresh ideas were impressive. He contributes to open-source projects in his free time." | ✅ | "Fresh ideas" describes idea novelty, not age. Assessment backed by evidence (open-source contributions). |
| IF-OK4 | "Susan came across as conservative in her approach, unwilling to cut corners. Exactly the temperament we need." | ✅ | "Conservative" describes risk appetite in a risk management context. Job-relevant competency. |
| IF-OK5 | "Rajesh demonstrated physical readiness during the fitness drill and showed controlled assertiveness in the scenario." | ✅ | Grounded in observed performance. Behavioural descriptors, not identity markers. |

#### Unacceptable

| ID | Text | Verdict | Bias | Reasoning |
|----|------|---------|------|-----------|
| IF-NO1 | "Candidate is 38 and married with a child — we doubt he'll have the stamina. Rejected for age and family status." | ❌ | Age, Marital Status, Family Responsibility | Assumptions about stamina based on personal characteristics. TAFEP requires individual assessment. |
| IF-NO2 | "She's a small-built woman, won't manage the physical demands. We'll stick with a male hire." | ❌ | Gender | Gender-based assumption about physical capability. Assess through practical tests, not stereotypes. |
| IF-NO3 | "Candidate is 50 and set in his ways. Too old to learn new tricks. Rejected." | ❌ | Age | Age-based stereotyping about learning ability. Assess through evidence, not age. |
| IF-NO4 | "Candidate is only 25 — too young to be cautious. Also, she's newly married so might leave soon." | ❌ | Age, Marital Status, Gender | Age stereotyping plus marital status used to predict flight risk. Both prohibited. |
| IF-NO5 | "Candidate is Indian — might not blend in. We want someone who looks physically intimidating, like a Malay or Chinese." | ❌ | Race | Racial stereotyping. No GDOR defence possible. Completely unlawful. |

---

### 3C. Promotion Write-ups

#### Acceptable

| ID | Text | Verdict | Reasoning |
|----|------|---------|-----------|
| PW-OK1 | "John consistently demonstrates a relentless work ethic and killer instinct for closing mandates. His youthful energy and resilience make him ready for Associate." | ✅ w/ justification | "Youthful energy" borderline, but tied to demonstrated outcomes (closing mandates). Defensible GDOR for high-intensity role. |
| PW-OK2 | "Mei is an empathetic and collaborative leader. She mentors juniors and builds a psychologically safe environment. Her style has lifted morale and delivery quality." | ✅ w/ justification | "Empathetic" and "nurturing" are feminine-coded but tied to measurable leadership outcomes. Genuine competencies, not gender proxies. |
| PW-OK3 | "Ahmed's greatest strength is his prudence. His steady, seasoned judgment has prevented several limit breaches." | ✅ w/ justification | "Seasoned" could imply older, but judgment is tied to documented outcomes. Defensible GDOR. |
| PW-OK4 | "Hani commands respect. He is firm and decisive in enforcing protocols. His approach has reduced incidents by 30%." | ✅ w/ justification | "Firm" and "decisive" tied to safety outcomes. Leadership competencies, not gender preference. |
| PW-OK5 | "Mary is exceptionally reliable and process-driven. Her consistent, error-free output sets the standard." | ✅ | Performance descriptors based on documented track record. No protected characteristic referenced. |

#### Unacceptable

| ID | Text | Verdict | Bias | Reasoning |
|----|------|---------|------|-----------|
| PW-NO1 | "We need a masculine, hard-charging leader. Sarah is too soft and collaborative — lacks the aggressive edge expected of a male MD." | ❌ | Gender | Explicit gender preference. Promotion must be based on objective performance, not gender-based assumptions. |
| PW-NO2 | "Priya is our best coder but we can't promote her — she's pregnant and will go on maternity leave." | ❌ | Pregnancy, Gender, Family Responsibility | TAFEP states pregnancy must not affect promotion. Decisions based on past performance, not leave plans. |
| PW-NO3 | "Wei Ling is too timid and emotional to stand up to aggressive traders. We need someone more assertive and male." | ❌ | Gender | Gender stereotyping. Assertiveness is assessable across all genders. |
| PW-NO4 | "Ahmad is great but we can't make him supervisor — his prayer breaks interfere with shift handovers." | ❌ | Religion | Must make reasonable accommodations for religious practices before denying promotion. |
| PW-NO5 | "Promote Raj because he's one of the guys and fits the Chinese-speaking environment." | ❌ | Race, Gender | In-group preference based on race and gender. Social language use is not a job requirement. |

---

## 4. TAFEP References

| Document | When It Applies |
|----------|-----------------|
| Tripartite Guidelines on Fair Employment Practices | All documents, all bias categories |
| "What is a Discriminatory Job Advertisement?" | JD screening |
| Guide on Performance Appraisals and Promotions | Promotion write-up screening |
| Guidelines on Pregnancy and Maternity | Pregnancy/family bias |
| Guide on Religious Accommodation | Religious bias |
| Fair Consideration Framework (FCF) | Overall compliance |

Available at **tafep.sg**

---

## Appendix: Example Index

| ID | Type | Verdict | Bias |
|----|------|---------|------|
| JD-OK1 | JD | ✅ | — |
| JD-OK2 | JD | ✅ J | Physical ability |
| JD-OK3 | JD | ✅ | — |
| JD-OK4 | JD | ✅ | — |
| JD-OK5 | JD | ✅ J | Physical ability |
| JD-NO1 | JD | ❌ | Age, Marital, Family |
| JD-NO2 | JD | ❌ | Gender |
| JD-NO3 | JD | ❌ | Age |
| JD-NO4 | JD | ❌ | Age |
| JD-NO5 | JD | ❌ | Race, Gender |
| IF-OK1 | Interview | ✅ | — |
| IF-OK2 | Interview | ✅ | — |
| IF-OK3 | Interview | ✅ | — |
| IF-OK4 | Interview | ✅ | — |
| IF-OK5 | Interview | ✅ | — |
| IF-NO1 | Interview | ❌ | Age, Marital, Family |
| IF-NO2 | Interview | ❌ | Gender |
| IF-NO3 | Interview | ❌ | Age |
| IF-NO4 | Interview | ❌ | Age, Marital, Gender |
| IF-NO5 | Interview | ❌ | Race |
| PW-OK1 | Promotion | ✅ J | Age (potential) |
| PW-OK2 | Promotion | ✅ J | Gender-coded |
| PW-OK3 | Promotion | ✅ J | Age (potential) |
| PW-OK4 | Promotion | ✅ J | Gender-coded |
| PW-OK5 | Promotion | ✅ | — |
| PW-NO1 | Promotion | ❌ | Gender |
| PW-NO2 | Promotion | ❌ | Pregnancy, Gender, Family |
| PW-NO3 | Promotion | ❌ | Gender |
| PW-NO4 | Promotion | ❌ | Religion |
| PW-NO5 | Promotion | ❌ | Race, Gender |

*✅ J = acceptable_with_justification*