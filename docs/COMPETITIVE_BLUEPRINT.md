# EduFlow: benchmark and execution blueprint

Research date: October 2, 2026. Evidence below comes from public first-party product
pages and project descriptions, not hands-on access to paid products. Vendor claims
are not independently measured. Hackathon examples are submissions; no prize status
was established. The proposed differentiators are hypotheses to test with teachers,
not claims that no competing tool has ever implemented them.

## Five benchmarks

| Product | Documented value | Current EduFlow gap | Adaptation in this build |
|---|---|---|---|
| [MagicSchool](https://www.magicschool.ai/tools/lesson-plan) | Standards and objectives feed structured lesson planning and differentiation. | Extracted objectives lack a direct route into timetable setup. | Guided source-to-plan flow with objective selection and teacher-defined teaching time. |
| [Brisk Intelligence](https://www.briskteaching.com/curriculum-intelligence) | Adopted curriculum, pacing, resource collections, and leadership visibility inform AI output. | Sources and curriculum nodes live in a global pool with weak document attribution. | Persistent document-to-objective associations, extraction reuse, and visible evidence gaps. |
| [Common Planner](https://www.commonplanner.com/) | Daily planning, standards coverage, team planning, and contextual notes share one planbook. | The product opens on a source form rather than showing a teacher's next action. | An Overview with plan switching, objective coverage, and actionable gaps. |
| [Planbook](https://help.planbook.com/overview-lesson-actions) | Bump/extend lessons and inspect standards coverage. | Disruption applies immediately, before the teacher can judge time lost or objectives omitted. | Recovery Lab compares preserve-depth, balanced, and coverage-first outcomes before an atomic apply. |
| [LessonLoop](https://devpost.com/software/lessonloop-7fg5pa) | Hackathon submission connects standards, class evidence, teacher context, and editable 5E plans. | Scheduled coverage can be mistaken for teaching readiness. | Coverage ledger separates planned/taught status, source attribution, and verified-claim availability. |

Planbook's [standards reporting](https://help.planbook.com/knowledgebase/articles/2011622-how-to-report-on-standards-taught)
also establishes coverage reporting as a baseline expectation. Our distinction is to
put its gaps beside evidence readiness and the consequences of a disruption.

## Product direction

**A teacher's control room for keeping a term on track.** Sources determine what
belongs in the plan. The solver shows what fits. Teachers see the consequences and
choose the recovery. Evidence stays inspectable throughout.

### Iteration 1: close the real workflow gaps

1. Persist source-to-curriculum attribution and extraction fingerprints. Repeated
   extraction of unchanged material reuses stored nodes, saving credits and duplicates.
2. Let teachers select objectives, dates, weekly lesson days, session length, and
   expected teaching time from Sources. Create the calendar, teaching units, and plan
   in one transaction. Missing prerequisites must be explained, not silently discarded.
3. Store the selected curriculum in plan metadata. Switching plans restores the
   correct class, subject, scope, and controls rather than trusting stale browser state.

### Iteration 2: make consequences visible before committing

1. **Recovery Lab:** evaluate one closure against three explicit strategies. Display
   weighted coverage, lost minutes, shortened units, moved sessions, and omitted
   objectives. All comparisons use the real solver and taught-session locks.
2. Persist a bounded scenario snapshot with a fingerprint of the baseline timetable.
   Applying a scenario must reject stale input, preserve the exact reviewed solution,
   and atomically update closures plus the new plan version.
3. **Coverage and evidence ledger:** distinguish unscheduled, planned, partially
   taught, and taught objectives; show attributable source counts and verified claims
   independently. A scheduled lesson must not imply factual or pedagogical verification.

### Iteration 3: presentation and polish

1. Graphite navigation, crisp high-contrast type, electric blue actions, restrained
   lime accents, responsive cards, strong keyboard focus, and reduced-motion support.
2. Make Overview the opening screen. A large coverage visual and concrete next action
   establish the story before the audience sees the detailed controls.
3. Keep Sources, Planner, and Evidence focused. Put the Recovery Lab in a wide compare
   view where differences are readable without opening multiple drawers.
4. Use the working API for every metric and comparison. No invented savings or scores.

### Iteration 4: verification

Test extraction reuse and invalidation, document isolation, transactional setup,
preview-without-mutation, exact scenario application, stale scenario rejection,
duplicate application, taught locks, and honest coverage/evidence counts. Run the
existing suite and a browser walkthrough covering custom setup, recovery, plan
switching, evidence, responsive layout, and keyboard interaction.

## Three-minute pitch

- **0:00:** “A good lesson plan fails the moment the timetable changes.” Show the
  term overview, planned coverage, and evidence gaps with original demo data.
- **0:30:** Show a syllabus linked to its own objectives. Open the source behind one.
- **1:00:** Enter two closures. Recovery Lab shows the actual cost of preserving
  lesson depth versus shortening permitted units to protect coverage.
- **1:45:** Choose a strategy. Animate the exact reviewed plan into place; taught
  sessions stay locked. Show the coverage ledger update.
- **2:15:** Inspect an evidence-backed claim and export the timetable.
- **2:45:** State measured regression results and remaining pilot limitations. The
  value is explainable decisions under constraints, not a promise of perfect AI.

## Implementation delivered

- Source-specific objective lists and extraction cache with content fingerprint
  invalidation. Long inputs prioritize objective-rich passages and disclose partial
  extraction. Previously attributed demo objectives remain usable.
- A teacher-reviewed wizard creates a calendar, teaching windows, missing teaching
  units, and the first plan in one transaction. Existing unit definitions are reused.
- Coverage ledger separates scheduled, in-progress, taught, source attribution,
  and verified lesson claims. It supports objective search and lesson inspection.
- Recovery Lab solves three bounded alternatives, stores the exact assignments,
  and applies the selected option transactionally. Input fingerprints, expiry,
  taught-session locks, and duplicate-application protection guard the review flow.
- Graphite navigation, blue/lime contrast, responsive overview and comparison
  cards, saved-plan switching, source-scoped maps, and keyboard-accessible dialogs.
- Migration `0004` persists source caches and recovery decisions. The local review
  database has the new tables. PostgreSQL execution has not been tested locally.
- Automated integration checks cover preview without calendar mutation, exact
  reviewed assignments, stale comparisons, repeat application, source isolation,
  unit reuse, extraction cache reuse/invalidation, and evidence-count semantics.
  Browser scripts cover custom setup, plan switching, recovery, evidence rendering,
  exports, command palette, and overflow checks on all four mobile surfaces.

## Remaining boundaries

### Verification on 2026-10-02

- `python -m pytest -q`: **210 passed, 1 skipped**.
- `python -m mypy app`: **73 source files, no errors**.
- `python -m ruff check app tests eval`: passed.
- JavaScript syntax checks for both workspace scripts: passed.
- Both Playwright walkthroughs passed. Screenshots were visually reviewed for
  the overview and Recovery Lab; all four mobile surfaces passed overflow checks.
- Synthetic regression evaluation: precision@1 1.0 on 20 cases, six mechanical
  grounding checks passed, one moved unit versus eight for the naive rebuild,
  and zero hard-constraint violations. These are regression fixtures, not evidence
  of real-world teacher outcomes or semantic generation accuracy.

This build remains single-tenant and does not claim department access control or live
collaboration. Production identity/tenant isolation and durable workers require a
separate deployment design. Extraction output still needs teacher review. Neither
the coverage metric nor mechanical citation integrity proves student learning.
