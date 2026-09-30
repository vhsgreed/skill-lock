# RFC post draft — for r/clawdbot, Hacker News (Show HN), or the agentskills.io governance
# discussion. NOT posted anywhere yet: Karl reviews and posts from his own accounts.

**Title:** skills-lock.json — proposal for an open lockfile standard for agent skills (draft-01)

---

Agent skills went from one vendor's feature to a cross-vendor standard in under nine months
(~40 compatible platforms, ~1.9M indexed skills). Distribution is solved. Integrity is not.

Three attack primitives are already documented in the wild (Orca Security, "Skill Issues",
2026; Snyk "ToxicSkills", 2026):

1. **Silent override** — installing a same-named skill replaces the installed one, no
   warning, no diff.
2. **Blind bulk updates** — `update` refreshes everything at once; a skill benign at install
   time can be malicious one update later, with no review step and no pinning.
3. **Bait-and-switch** — clean at scan time, malicious at fetch time; nothing notices the
   content drift after trust was granted.

npm solved this class with `package-lock.json`. Skills have hashes in places — Vercel's
`skills` CLI tracks `skillFolderHash` in `~/.agents/.skill-lock.json`, HappySkills writes a
`skills-lock.json` — but as far as I can tell there is **no open spec that defines the
semantics**: what a pin guarantees, what statuses `verify` returns, what an update is
allowed to rewrite, and what happens when two skills share a name. (Vercel's own issue
#283 is essentially asking for these semantics.)

So here's a draft: **skills-lock.json (draft-01)** —
https://github.com/vhsgreed/skill-lock/blob/main/SPEC.md

What it specifies, in one breath:

- per-file **SHA-256 pins + a tree hash** per bundle (the single-value identity),
- a four-status verify model: `verified` / `modified` (with changed file names) /
  `missing` / `untracked`,
- **per-skill updates only**: re-pin one skill after listing its changed files; bulk update
  must be an explicit bulk flag; every other pin stays byte-identical,
- **fail on name shadowing** (two bundles, one name) — the silent-override precondition,
- reserved `source` and `attestations` fields so provenance and signatures (Sigstore,
  `skill.sig`) can layer on without breaking the format.

What it deliberately does NOT do: scanning (that's a judgment layer — I also built
`skillguard`, a SARIF-emitting scanner for skill backdoors, for that), trust decisions
(pins say "this is what was reviewed", not "this is safe"), and distribution (registries
build on `source`). TOFU is the honest trust model; scan at lock time.

There's a working stdlib-only reference implementation (`skilllock lock/verify/update`),
15 behavior tests, and a dogfood run pinning 58 live skills — tamper detection and the
update review gate shown working in the README.

Where I'd especially like pushback:

- **Field shape** — is the relative-path key right, or should bundles have stable IDs?
- **Vercel interop** — their lock entry shape (`source`, `sourceType`, `sourceUrl`,
  `skillFolderHash`) is close; a mapping table in the spec would make adoption cheap.
  If someone from that thread is here, what would make `skills sync` (#283) spec-shaped?
- **Tree hash definition** — concat `path\0digest\n` sorted; any prior art that does it
  differently and better?
- **What breaks at scale** — monorepos with 500 skills, generated skills, optional files?

Happy to iterate the draft in the open. If the shape is wrong, better to find out now
before anyone codes against it.

— Karl (github.com/vhsgreed)

---

## Posting notes (for whoever posts this)

- Post points at `github.com/vhsgreed/skill-lock` — push the repo FIRST, or edit the link.
- Good targets: r/clawdbot (the OpenClaw community thread that already discusses skill
  security), Show HN (title fits), the agentskills.io governance discussion.
- The tone is deliberate: evidence-first, asks for criticism, no marketing. Do not add
  superlatives; the ecosystem has hype fatigue and the credibility comes from the corpus
  + limitations sections being honest.
