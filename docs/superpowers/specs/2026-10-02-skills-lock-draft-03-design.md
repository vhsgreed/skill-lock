# skills-lock.json draft-03 design — source semantics, update-fetch rule, interop

Date: 2026-10-02. Author: Karl Sundström (positions) + Hermes Agent (draft).
Approved positions (Karl, 2026-10-02): the five decisions below are agreed at position
level; technical correctness is verified by code review, not by human review of the diff.

## Goal

Move agentskills/agentskills discussion #588's open questions Q1 and Q3 from "questions"
to decided: draft-03 answers both normatively, plus the interop mapping table. Q2 is
closed in the thread reply (tree hash stays normative, no spec change). Q4 (governance
home) stays open. Scope excludes evidence MUST-upgrade, scale rules, and stable bundle IDs.

## Decisions (the positions to defend)

1. **Two records for provenance.** `source` becomes `null | {type, resolved, declared}`.
   `resolved` = URL the installer actually fetched from (tool-written receipt; null when
   the bundle was never fetched). `declared` = verbatim mirror of SKILL.md
   `metadata.source` (the #564 author-declared field). `type` = git | url | registry |
   vendor | local. Mismatch `declared != resolved` is legitimate (mirror, vendoring):
   tools MAY warn, MUST NOT fail. Rationale: one field can only record one of the two
   facts; update tooling needs the receipt, humans and #564 compatibility need the claim.

2. **Update fetch rule (security core).** Update MUST fetch from `resolved`. When
   `resolved` is null and `declared` exists (manual install, the #564 case), one update
   MAY fetch from `declared`, after which the tool MUST record the actual `resolved` and
   re-pin under normal per-skill update semantics. Update MUST NOT fetch from any URL
   appearing in bundle *content*: a modified SKILL.md must not be able to redirect its
   own update (update-hijack). This is what makes the #564 answer safe.

3. **Q3: per-skill unit AND review step, both normative.** Tools choose the UI, never the
   unit. Draft-02 §5 already says MUST NOT bulk-update without an explicit flag; draft-03
   adds one sentence answering the thread question outright.

4. **Interop mapping table (appendix).** `source.resolved` <-> Vercel `sourceUrl`,
   `source.type` <-> `sourceType`, `source.declared` <-> #564 `metadata.source`,
   `tree_hash` <-> `skillFolderHash`. Honest footnote: `skillFolderHash` uses a different
   algorithm; the mapping is structural, digests are not interchangeable. `files.*` has no
   Vercel counterpart (they track one folder hash); that gap is the value proposition.

5. **Honest limitation, written down.** `source` fields are not covered by `tree_hash`
   (which spans `files` only). A tampered lockfile can redirect updates while all file
   hashes verify. Mitigation is the existing one: commit lockfiles to VCS and review
   diffs. Stated in Security considerations so a critic cannot write it first.

## Spec changes (SPEC.md, bump to draft-03)

- §3: `source` shape and field semantics (replacing "reserved, null in draft-02").
- §5: update-fetch rule paragraph (decision 2) + the one-sentence Q3 answer (decision 3).
- §7: "no distribution" bullet adjusted: `source` now has defined semantics but
  registry protocols remain out of scope.
- §8: security considerations addition (decision 5).
- New appendix: interop mapping table (decision 4).

## Reference implementation changes (skilllock)

- `lock`: parse `metadata.source` from SKILL.md frontmatter into `source.declared`;
  accept `--source-url` / `--source-type` to record `resolved` when known; `type`
  defaults per origin (local when locking a plain directory).
- `update`: fetch fallback to `declared` when `resolved` is null, then record `resolved`;
  refuse content-embedded URLs (already implicit; make the rule test-visible).
- Unknown-field preservation on rewrite already exists; `source` object must round-trip.

## Test plan (TDD: tests first, watch them fail)

Corpus additions (samples/):
- benign skill with `metadata.source` frontmatter (must raise zero findings in skillguard;
  must populate `declared` in skilllock).
- mismatch case: `declared` differs from recorded `resolved` (warn, not fail).
- hijack sample: skill content carrying an update URL (must never be used; test-visible).

Behavior tests (skilllock):
- lock records declared from frontmatter, resolved from flags, type defaults.
- update-from-declared flow: resolved null -> fetch from declared -> resolved recorded,
  re-pin under per-skill semantics.
- source object round-trips through a rewrite with unknown keys preserved.

## Deliverables

1. SPEC.md draft-03 (committed in skill-lock).
2. skilllock implementation + tests (committed).
3. docs/rfc-post.md refreshed to match reality (draft-03, real test count, five statuses).
4. Thread-reply draft for #588: Q1 and Q3 answered as decided, Q2 closed in one line,
   Q4 left open, one-line defense per decision. Karl posts it from his own account.

## Out of scope (this round)

Evidence SHOULD->MUST upgrade, scale rules (optional files, generated skills, monorepos,
partial locks), stable bundle IDs. None are blocked by draft-03; all can land as draft-04.

## Addendum 2026-10-02, sixth decision (from James Ross on #588)

Verify before load (new normative rule, SPEC 4.3): an installer unpacks in a staging
location the harness cannot see, verifies there, and only then moves a verified tree into
the load path. Attack: a tree unpacked inside a workspace gets registered by the harness at
first read, before any verify runs. Defense: a check that runs after a harness can see the
tree is a receipt about an accident that already happened. Cross-referenced to James Ross's
hook-plus-acknowledgement pattern (agent-workspace-architecture PATTERNS.md #7), which
remains valid defense in depth. The reply draft acknowledges his comment and states the rule.
