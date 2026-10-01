# Outreach drafts — skill-lock (2026-09-30). No em dashes in any of these (Karl's rule).
# Nothing here is posted. Karl pulls the trigger.

════════════════════════════════════════════════════════════════
1. COMMENT ON vercel-labs/skills#283
════════════════════════════════════════════════════════════════

Drafted an open spec + reference implementation for exactly this: https://github.com/vhsgreed/skill-lock (SPEC.md, draft-01).

What it adds on top of the current `.skill-lock.json` shape (which I read as an update-tracking DB):

- install/sync semantics: what a pin guarantees, per-file sha256 + a tree hash per bundle
- a verify model: `verified` / `modified` (with changed file names) / `missing` / `untracked`
- per-skill update only: re-pin one skill after listing its changed files, every other pin stays byte-identical (kills the blind-bulk-update problem)
- fail on duplicate skill names across bundles (the silent-override precondition)
- reserved `source` / `attestations` fields for provenance and signatures (Sigstore, skill.sig)

Two questions for this thread:

1. For `skills sync` to be spec-shaped, what is missing? (e.g. project-local vs global lock precedence, `--missing-only`, dry-run semantics)
2. Your entry shape (`source`, `sourceType`, `sourceUrl`, `skillFolderHash`, `installedAt`, `updatedAt`) maps cleanly into the draft. A mapping table in the spec would make interop cheap and I am happy to add one.

Working CLI (`skilllock lock/verify/update`), 15 behavior tests, dogfooded on 58 live skills. The field shape is draft on purpose, so push back on it.

════════════════════════════════════════════════════════════════
2. REDDIT POST (r/clawdbot first; reusable on r/LocalLLaMA, r/ChatGPTCoding)
════════════════════════════════════════════════════════════════

Title: skills-lock.json: draft spec for an open lockfile standard for agent skills (pinning, per-skill updates, shadow detection)

Body:

Skills went from one vendor's feature to a cross-vendor standard in under nine months (about 40 compatible platforms, ~1.9M indexed skills). Distribution is solved. Integrity is not. Three attack primitives are already documented in the wild (Orca's "Skill Issues" research, Snyk's ToxicSkills study):

1. Silent override: install a skill with the same name as an installed one and it gets replaced. No warning, no diff.
2. Blind bulk updates: update refreshes everything at once. A skill that was clean at install time can be malicious one update later, with nothing to review.
3. Bait and switch: clean at scan time, malicious at fetch time. Nothing notices the drift after you decided to trust it.

npm fixed this class of problem with package-lock.json. Skills have hashes in places (Vercel's skills CLI tracks a folder hash in its global lock, HappySkills writes a skills-lock.json), but as far as I can tell nobody has published the semantics as an open spec: what a pin guarantees, what verify returns, what an update is allowed to rewrite, what happens when two skills share a name.

So here is a draft: https://github.com/vhsgreed/skill-lock (SPEC.md, draft-01)

In one breath it specifies:

- per-file sha256 pins plus a tree hash per bundle (the single-value identity)
- a four-status verify model: verified / modified (with the changed file names) / missing / untracked
- per-skill updates only: one skill re-pinned after its changed files are listed, every other pin byte-identical. Bulk update must be an explicit bulk flag
- hard failure on name shadowing (two bundles, one name)
- reserved fields for provenance and signatures later (Sigstore, skill.sig style)

What it deliberately does not do: scanning (that is a judgment layer, and I built a separate SARIF-emitting scanner for it: https://github.com/vhsgreed/skillguard), trust decisions (a pin says "this is what was reviewed", not "this is safe"), and distribution (registries can build on the reserved fields). Trust on first use is the honest default. Scan at lock time.

There is a stdlib-only reference implementation (skilllock lock/verify/update), 15 behavior tests, and a dogfood run pinning 58 live skills with the tamper check and the update review gate working.

Where I want pushback:

- field shape: relative-path keys, or do bundles need stable IDs?
- tree hash definition: concat "path\\0digest\\n" sorted, then sha256. Is there prior art that does it better?
- what breaks at scale: 500-skill monorepos, generated skills, optional files?
- Vercel interop: their lock entry maps onto the draft almost 1:1. What would make their open #283 (skills install/sync from lock) spec-shaped?

If the shape is wrong I would rather find out now than after anyone codes against it.

════════════════════════════════════════════════════════════════
3. SHOW HN
════════════════════════════════════════════════════════════════

Title: Show HN: skill-lock – a lockfile standard for agent skills (SKILL.md)

Body:

Agent skills (SKILL.md folders) became a cross-vendor standard in under nine months and now ship through registries with the supply-chain problems npm had before lockfiles: same-name installs silently replace installed skills, bulk updates pull the latest of everything with no review step, and a package that was clean at install time can change after you granted it trust. Security researchers have published working exploits of all three this year.

skill-lock is a draft open spec plus a reference implementation for the missing dependency-pinning layer: per-file SHA-256 pins and a tree hash per skill bundle, a verify model (verified / modified / missing / untracked), per-skill-only updates that list changed files before re-pinning, and hard failure on duplicate skill names (the silent-override precondition).

Spec: https://github.com/vhsgreed/skill-lock/blob/main/SPEC.md
Impl: stdlib-only Python, `skilllock lock/verify/update`, 15 behavior tests, dogfooded against 58 live skills.

Honest limitations, so you do not have to dig for them: the trust model is TOFU (a pin proves stability, not benignity), content scanning is intentionally out of scope (separate tool: https://github.com/vhsgreed/skillguard, a SARIF-emitting scanner for skill backdoors), and signature verification is a reserved field, not implemented yet.

The draft is deliberately unfinished. The parts I most want attacked: the tree-hash definition, relative-path bundle keys vs stable IDs, and behavior at 500+ skills.

Suggested first comment (HN convention, post right after the submission):

"Some context that did not fit the post: the trigger for this was the 2026 supply-chain research on skill marketplaces (Orca's four attack primitives, Snyk finding prompt injection in 36% of tested skills). The specific design decision worth arguing about is per-skill-only updates: the spec forbids a bulk update without an explicit bulk flag, because 'update refreshed everything' is exactly how a clean-at-install skill turns malicious with nothing to review. Also happy to answer questions about the SARIF side (skillguard), which exists because SAST scanners currently have no detection category for skill backdoors at all."
