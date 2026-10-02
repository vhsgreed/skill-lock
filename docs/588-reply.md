# Reply draft for agentskills discussion #588
# NOT posted yet. Karl reviews and posts from his own account.
# https://github.com/agentskills/agentskills/discussions/588
# Plain language on purpose: Karl signs it and must be able to defend every line.

---

Draft-03 is up and it answers Q1 and Q3 normatively, plus the interop table someone asked
for. Q2 I think resolves itself in one line. Q4 is still open and I can't settle it alone.

Spec: https://github.com/vhsgreed/skill-lock/blob/main/SPEC.md
(commits today; reference implementation updated, 37 behavior tests green)

**Q2, one line:** the tree hash stays the normative identity of a bundle and the per-file
map is what names changed files; they do different jobs, so there is nothing to choose
between them.

**Q1: where does a skill's source canonically live?** In the lockfile. Draft-03 records
provenance as two fields on purpose:

- `source.resolved`: the exact URL the installer actually fetched from. A receipt, written
  by the tool, never by a human.
- `source.declared`: a verbatim mirror of the author's `metadata.source` frontmatter key
  (the proposal from #564). A claim.

They can legitimately differ (mirrors, vendoring, a repo subpath vs. its clone URL), so a
mismatch raises a warning, never a failure. This is the division npm settled on: the
manifest may suggest, the lock records.

Why two fields instead of one? Because either single answer is attackable. Frontmatter as
authority means a skill can name its own update origin (update-hijack). Lockfile only
leaves manually installed skills, the #564 case, with no answer at all.

The rule that makes it safe is short: **updates fetch from the pinned `resolved`, and never
from any URL found inside the skill's content.** If there is no receipt (hand-copied
skill), one update MAY fetch from the pinned `declared`, then MUST record where the bytes
really came from as the new `resolved` and re-pin. The fallback closes itself after one
use. The reference implementation enforces this structurally: `resolve_update_source()`
can only read the pinned entry, so a bundle's own content cannot feed the fetch decision.

**Q3: per-skill update default.** Made normative. The unit of update is one named skill and
the review step (show the changed files before anything is written) is mandatory. Tools are
free to choose their UI; they do not get to choose the unit. Draft-03 also adds an explicit
`locally_modified` flag to the changes summary so tools stop inferring it.

**@zzzz0902zzzz-rgb** -- all four of your points landed in draft-02 and they made the spec
better; draft-03 keeps them:

1. bare "no" is gone: every non-verified entry carries a machine-readable reason payload
   (which files, which digests, where the lookup searched), credited to your review
   (SPEC 4.1),
2. changed-file attribution is digest-only and normative (SPEC 4.2),
3. updates are fail-closed and atomic: on any failure the old pins remain byte-identical
   (SPEC 5),
4. cache and mirror fallbacks report `unverified-source` instead of failing silently.

On evidence files: kept at SHOULD, with `--evidence DIR` in the reference implementation.
My reason is that per-attempt logging is runner policy, not lockfile semantics; I don't
want conformant lockfile parsers failing over log handling. If you can state what a
lockfile consumer can observe that makes MUST enforceable, I'll upgrade it in draft-04.

**Interop:** Appendix A maps our fields to Vercel's `sourceUrl`/`sourceType`/
`skillFolderHash` and to #564's `metadata.source`. Honest footnote in the table:
`skillFolderHash` and `tree_hash` are structural counterparts only; different algorithm,
different input set, the digest numbers do not verify against each other.

**Q4 (governance) is still open.** Where should this live to get real cross-vendor review?
I have opinions but no standing to appoint a home for it, so: input wanted.

Design decisions, one line each, so follow-ups don't have to re-derive them:

- Two records: a claim and a receipt are different objects; either one alone is attackable.
- Fetch from the receipt: a skill must never name its own update origin.
- One-shot fallback: manually installed skills need an answer, and the receipt written
  after the first fetch closes the hole.
- Per-skill + review mandatory: bulk-by-default is exactly attack primitive 2.
- `source` outside the tree hash: stated as a limitation, not hidden; lockfile-in-git with
  reviewed diffs until signing lands.

-- Karl (github.com/vhsgreed)

---

## Optional one-liner for #564 (davinwang), separate comment

Good news: `metadata.source` is now normative in draft-03, appendix A.1 (both the nested
`metadata:` block form and the flat `metadata.source:` form). It is mirrored into
`source.declared` in the lockfile at pin time, which is where tooling reads it. Reason it
is a mirror and not the authority: frontmatter travels inside the very content whose
provenance it declares, so updates must not trust it for fetching. Spec link as above.

## Posting notes

- Push the repo before posting; the SPEC.md link must resolve.
- Post order: main reply first, then the #564 one-liner.
- Q4 must stay open in the text; do not let the thread read as if governance is decided.
