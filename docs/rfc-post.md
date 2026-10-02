# RFC post draft -- for r/clawdbot, Hacker News (Show HN), or the agentskills.io governance
# discussion. NOT posted anywhere yet: Karl reviews and posts from his own accounts.

**Title:** skills-lock.json -- proposal for an open lockfile standard for agent skills (draft-03)

---

Agent skills went from one vendor's feature to a cross-vendor standard in under nine months
(~40 compatible platforms, ~1.9M indexed skills). Distribution is solved. Integrity is not.

Three attack primitives are already documented in the wild (Orca Security, "Skill Issues",
2026; Snyk "ToxicSkills", 2026):

1. **Silent override** -- installing a same-named skill replaces the installed one, no
   warning, no diff.
2. **Blind bulk updates** -- `update` refreshes everything at once; a skill benign at install
   time can be malicious one update later, with no review step and no pinning.
3. **Bait-and-switch** -- clean at scan time, malicious at fetch time; nothing notices the
   content drift after trust was granted.

npm solved this class with `package-lock.json`. Skills have hashes in places -- Vercel's
`skills` CLI tracks `skillFolderHash` in `~/.agents/.skill-lock.json`, HappySkills writes a
`skills-lock.json` -- but as far as I can tell there is **no open spec that defines the
semantics**: what a pin guarantees, what statuses `verify` returns, what an update is
allowed to rewrite, and what happens when two skills share a name. (Vercel's own issue
#283 is essentially asking for these semantics.)

So here's a draft: **skills-lock.json (draft-03)** --
https://github.com/vhsgreed/skill-lock/blob/main/SPEC.md

What it specifies, in one breath:

- per-file **SHA-256 pins + a tree hash** per bundle (the single-value identity),
- a five-status verify model: `verified` / `modified` / `missing` / `untracked` /
  `unverified-source`, where every non-verified entry carries a machine-readable reason
  payload (which files changed and to which digests, where a lookup searched),
- **per-skill updates only**: re-pin one skill after listing its changed files; bulk update
  must be an explicit bulk flag; every other pin stays byte-identical; the review step is
  mandatory and the changes summary carries an explicit `locally_modified` signal,
- **provenance as two records** (`source.resolved` = where the installer actually fetched
  from, `source.declared` = the author's `metadata.source` claim from the frontmatter),
  with an update-fetch rule: updates fetch from the pinned receipt, one-shot fallback to
  the declared URL for manually installed skills, never from URLs found in skill content
  (that is update-hijack),
- **fail on name shadowing** (two bundles, one name) -- the silent-override precondition,
- reserved `attestations` for signatures (Sigstore, `skill.sig`), and an interop appendix
  mapping our fields to Vercel's `sourceUrl`/`sourceType`/`skillFolderHash` and to the
  `metadata.source` frontmatter key discussed in agentskills #564.

What it deliberately does NOT do: scanning (that's a judgment layer -- I also built
`skillguard`, a SARIF-emitting scanner for skill backdoors, for that), trust decisions
(pins say "this is what was reviewed", not "this is safe"), and distribution (registries
build on `source`). TOFU is the honest trust model; scan at lock time.

Honest limitation, stated in the spec: `source` is provenance, not integrity -- it is not
covered by the tree hash, so the mitigation for a tampered lockfile is the boring one
(lockfile in git, reviewed diffs). Signing is the real fix and `attestations` is the slot
for it.

There's a working stdlib-only reference implementation (`skilllock lock/verify/update`),
37 behavior tests (including an update-hijack-attempt corpus), and a dogfood run pinning 58
live skills -- tamper detection and the update review gate shown working in the README.

Where I'd especially like pushback:

- **Stable bundle IDs** -- is the relative-path key right at scale, or should bundles carry
  a stable identifier independent of where they sit on disk?
- **What breaks at scale** -- monorepos with 500 skills, generated skills, optional files,
  partial locks?
- **Evidence: SHOULD or MUST?** -- draft-03 keeps per-attempt evidence logs at SHOULD
  (runner policy, not lockfile semantics). If you think a lockfile consumer can observe
  enough to make it MUST, say what.
- **Governance home** -- where should a spec like this live to get real review? (Open
  thread in the agentskills discussion.)

Happy to iterate the draft in the open. If the shape is wrong, better to find out now
before anyone codes against it.

-- Karl (github.com/vhsgreed)

---

## Posting notes (for whoever posts this)

- Post points at `github.com/vhsgreed/skill-lock` -- push the repo FIRST, or edit the link.
- Good targets: r/clawdbot (the OpenClaw community thread that already discusses skill
  security), Show HN (title fits), the agentskills.io governance discussion.
- The tone is deliberate: evidence-first, asks for criticism, no marketing. Do not add
  superlatives; the ecosystem has hype fatigue and the credibility comes from the corpus
  + limitations sections being honest.
- Zero em dashes (house style); the double hyphens above stand in for them.
