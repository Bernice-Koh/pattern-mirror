# 5. SonarCloud integration

- Status: Accepted
- Date: 2026-06-21

## Context

ADR 0004 stood up the CI pipeline but deferred the SonarCloud scan named in issue #18,
on the assumption it was an extra provisioning and cost burden. Revisiting it to close
#18: the assumption was wrong in our favour. SonarCloud (rebranded *SonarQube Cloud*) now
analyses **private** repositories up to 50,000 lines of code on its **free** tier,
including branch analysis, PR decoration, and quality-gate enforcement. The repo is ~2.7k
LOC, so the scan and gate cost nothing.

## Decision

- **SonarCloud, not self-hosted SonarQube.** The free Community Build of self-hosted
  SonarQube has no PR analysis, and self-hosting a server earns nothing for a project this
  size. SonarCloud is the tool the issue names and is free for us.

- **CI-based analysis, not Automatic Analysis.** The two modes are mutually exclusive.
  Automatic Analysis (SonarCloud scanning the repo server-side) cannot ingest test
  coverage — coverage only exists once tests run, which happens in CI. Issue #18 also reads
  the scan as a pipeline *step*. So Automatic Analysis is turned off and a `sonarcloud` job
  runs `SonarSource/sonarqube-scan-action` (the rename of the deprecated
  `sonarcloud-github-action`).

- **One Sonar project for the monorepo.** `sonar.sources` covers both `backend/src` and
  `frontend/src`; `backend/tests` is declared as tests. SonarCloud's true multi-project
  monorepo mode is a paid feature we don't need.

- **The `sonarcloud` job needs `backend`.** It downloads the backend's `coverage.xml`
  artifact (the only coverage we produce) and scans. `fetch-depth: 0` because Sonar's
  new-code detection and blame need full history. The frontend jobs stay parallel.

- **Backend coverage now via `pytest-cov`.** Backend tests already exist, so emitting
  `coverage.xml` is nearly free and gives the gate a real number. The frontend has no test
  framework yet, so it contributes no coverage.

- **Custom quality gate with the coverage condition removed (for now).** Cloned from
  "Sonar way", dropping *Coverage on New Code* while keeping the rating, security-hotspot,
  and duplication conditions. Demanding 80% new-code coverage against a test-less frontend
  would paint every frontend PR red and breed alarm fatigue — the gate would be ignored.
  The condition gets re-added when frontend tests land (tracked as a follow-up issue). This
  is the standard "clean as you code" ratchet: enforce what the codebase can satisfy, raise
  the bar as it earns it.

- **`sonar.qualitygate.wait=true`.** The scan blocks on the gate result and exits non-zero
  if it fails, so a red gate surfaces as a failing CI check.

## Consequences

- **+** Every PR gets static-analysis feedback (bugs, vulnerabilities, security hotspots,
  duplication, maintainability) on new code, plus a real backend coverage number.
- **+** Closes the SonarCloud half of issue #18 at no cost.
- **−** **Coverage is backend-only and not gated.** Until the frontend test foundation
  lands, new-code coverage is informational, not enforced.
- **−** **Still no merge enforcement.** Unchanged from ADR 0004: branch protection and
  required status checks remain unavailable on a free private repo, so the gate reports but
  cannot block a merge. The working convention stays "don't merge red". This is issue #18's
  last open dependency and is a billing/visibility decision, not an engineering one.
- **−** A `SONAR_TOKEN` repository secret must exist for the job to authenticate; the
  pipeline's `sonarcloud` job errors until it is provisioned, by design.

## Alternatives considered

- **Automatic Analysis** — rejected: cannot ingest coverage, and sits outside the pipeline
  the issue describes.
- **Self-hosted SonarQube Community Build** — rejected: no PR analysis on the free tier,
  plus server upkeep for no benefit at this scale.
- **A non-Sonar tool (CodeQL, Codacy, Qlty)** — rejected: CodeQL is security-SAST, not the
  coverage-and-maintainability gate the issue specifies, and #18 names SonarCloud outright.
- **Keep the default "Sonar way" gate** — rejected: its new-code coverage condition would
  fail on test-less frontend PRs, training the team to ignore the gate.
