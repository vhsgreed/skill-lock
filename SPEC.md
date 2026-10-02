# skills-lock.json — Open Specification (draft-03)

**Status:** draft, seeking comment. **Scope:** integrity pinning and update control for
agent skill bundles (`SKILL.md` + accompanying files), independent of any agent runtime.

## 1. Motivation

Agent skills ("SKILL.md" packages) became a cross-vendor standard in under nine months and
ship through registries that exhibit classic un-fixed supply-chain failures. Demonstrated
attack primitives (Orca Security, 2026; Snyk ToxicSkills, 2026):

1. **Silent override** — installing a same-named skill replaces the existing one with no
   warning or diff.
2. **Blind bulk updates** — `update` refreshes everything at once; a skill benign at install
   time can turn malicious on the next update, with no review step and no pinning.
3. **Bait-and-switch** — clean at scan time, malicious at fetch time; consumers have no way
   to notice content drift after trust was granted.

npm solved this class of problem with `package-lock.json` + content hashes. Skills have no
equivalent as an open format. This document specifies one.

## 2. Terminology

- **Bundle** — a directory containing `SKILL.md` and optional subdirectories
  (`references/`, `scripts/`, `assets/`, `templates/`).
- **Pin** — the recorded per-file content hashes and aggregate tree hash for one bundle at
  one point in time.
- **Lockfile** — `skills-lock.json`: the set of pins for a collection of bundles.

## 3. File format

A lockfile is UTF-8 JSON:

```json
{
  "version": 1,
  "generated_by": "skilllock 0.1.0",
  "skills": {
    "<relative-bundle-path>": {
      "name": "<skill name>",
      "version": "<skill version or null>",
      "files": {
        "SKILL.md": "sha256:<hex>",
        "references/notes.md": "sha256:<hex>"
      },
      "tree_hash": "sha256:<hex>",
      "source": {
        "type": "git",
        "resolved": "https://github.com/owner/repo.git",
        "declared": "https://github.com/owner/repo/tree/main/skills/skill-a"
      },
      "attestations": []
    }
  }
}
```

Field semantics:

- `skills` is keyed by the bundle path **relative to the lockfile's scan root**, using
  forward slashes. Paths MUST be relative; runtimes resolve them against their own root.
- `name` / `version` are extracted from the bundle's frontmatter; `name` defaults to the
  bundle directory name; `version` may be null.
- `files` maps every file in the bundle (excluding `.git`, `__pycache__`, virtualenv and
  `node_modules` directories) to the lowercase hex SHA-256 of its bytes, prefixed
  `sha256:`.
- `tree_hash` = SHA-256 over the concatenation of `"<path>\0<digest>\n"` for every entry of
  `files`, sorted by path. It is the single-value identity of the bundle.
- `source` records provenance as `null` (unknown) or an object of three fields
  (draft-03; this is the normative answer to discussion #588 Q1, "where does a skill's
  source canonically live?" — **in the lockfile**):
  - `type` — `git | url | registry | vendor | local`. Derived from `resolved` when
    possible. It is machine-assigned, never authored in SKILL.md.
  - `resolved` — the exact URL the installer fetched the bytes from. A receipt, written
    by the tool at install time; `null` if the bundle was never fetched (copied by hand,
    vendored, local).
  - `declared` — the author's claim: a verbatim mirror of the bundle's `metadata.source`
    frontmatter key if present (see Appendix A), else `null`.
- The two records are two records on purpose. `resolved` is evidence; `declared` is a
  claim. They may legitimately differ (mirrors, vendoring, a repo subpath vs. its clone
  URL). Tools MAY warn on mismatch; they MUST NOT fail on it. Where tooling needs one
  authoritative value, `resolved` wins: **the lockfile is authoritative, frontmatter is a
  hint** (npm's `package.json` vs. `package-lock.json` `resolved` split).
- `attestations` is reserved for signature envelopes (e.g. Sigstore, `skill.sig`);
  implementations MUST accept and preserve unknown entries here (forward compatibility).

Unknown top-level and per-skill fields MUST be preserved by tools that rewrite a lockfile.

## 4. Status model (`verify`)

For each pin in the lockfile and each bundle on disk:

| Status | Meaning |
|---|---|
| `verified` | bundle on disk hashes exactly to its pin |
| `modified` | bundle exists but files or hashes differ; the entry MUST carry a per-file delta (see below) |
| `missing` | pinned bundle absent from disk; the entry MUST carry the searched path(s) and the expected tree hash |
| `untracked` | bundle on disk with no pin |
| `unverified-source` | bundle content was resolved from a fallback (cache, mirror, vendored copy) rather than the installed disk path |

`verify` succeeds (exit 0) only if every status is `verified`.

### 4.1 Reasons are payloads, not prose

A bare status is not a diagnosis: a CI line that prints `tree hash mismatch` sends a human
bisecting. (Credit: the failure-visibility review by @zzzz0902zzzz-rgb on agentskills
discussion #588: "a failure must print why, a bare 'no' is the bug.") Every non-`verified`
entry MUST carry a machine-readable `reason` object:

- `modified`: `changed_files`, each entry `{path, kind: added|removed|modified, expected, actual}`
  where `expected`/`actual` are the pinned and observed per-file digests (`null` for
  added/removed sides).
- `missing`: `searched` (the resolved paths that were checked) and `expected` (the pinned
  `tree_hash`).
- `untracked`: `path` (the discovered bundle path).
- `unverified-source`: `resolved_from` (where the bytes actually came from) and `path`
  (where they were expected).

### 4.2 Localization is digest-only (normative)

Changed-file attribution MUST be computed from the per-file digest maps alone. Tools MUST
NOT localize changes via textual diff, content greps, or heuristics over file text:
text-based attribution produces both false greens (a real change dismissed as "just a
warning string") and false reds (an unchanged file blamed for scary-looking text). The
`tree_hash` is a cheap mismatch trigger only; it is not evidence and cannot name a file.
Evidence that names a file comes from digest comparison, full stop.

## 5. Update semantics (`update`)

A conforming tool MUST NOT provide a bulk update without an explicit bulk flag. The default
unit of update is **one named skill**. This is normative, not guidance: the per-skill unit
and the review step below are mandatory, and a tool may choose its UI but never the unit of
update (the normative answer to discussion #588 Q3). The changes summary an update produces
MUST carry a `locally_modified` boolean per touched bundle, so tools never infer it.

1. Re-hash only the named bundle.
2. Present the changed-file list to the operator (the review step). In non-interactive use,
   writing the new pin requires an explicit confirmation flag.
3. Rewrite only that bundle's pin; every other pin MUST remain byte-identical.

Update MUST be crash-safe and fail-closed: the new pin set is re-hashed and compared against
the bundle before it is committed, the lockfile is replaced atomically (write aside, then
rename), and on ANY failure (drift during update, read errors, interrupted write) the
previous pins remain in force, byte-identical. "Best effort" partial re-pins are forbidden:
a lockfile that has been through a failed update is either untouched or fully consistent.

### 5.1 The update-fetch rule (normative)

Where an update gets bytes from is decided by the **pinned lockfile entry alone**:

1. If `source.resolved` is pinned, update MUST fetch from `resolved`.
2. Else if `source.declared` is pinned, one update MAY fetch from `declared` — the one-shot
   fallback for manually installed bundles (the #564 case) — and MUST then record the URL
   the bytes actually came from as the new `source.resolved` and re-pin. The receipt step
   is part of the rule, not optional bookkeeping: after the first update, rule 1 applies.
3. Else (source `null`), there is no fetch source: update is a local re-pin and MUST NOT
   attempt any fetch.
4. Update MUST NOT fetch from any URL found in current bundle content (including
   `metadata.source` in the on-disk `SKILL.md`). Otherwise a modified skill could redirect
   its own update to an attacker-controlled URL while its content hashes verify —
   **update-hijack**. Fetch URLs come only from the pinned entry; the frontmatter's
   `metadata.source` may be refreshed into `source.declared` on re-pin (it is a claim, kept
   honest and current) but is never a fetch authority for a bundle that has a pinned
   `resolved`.

### 5.2 Evidence (SHOULD)

Verification and update runs SHOULD write their raw result payload to a per-attempt file
(distinct name per run; never truncate a previous attempt). This is runner policy rather
than lockfile semantics, which is why it is a SHOULD: forensically, re-running into the same
log destroys exactly the evidence a failed verification created. The reference
implementation demonstrates this with `--evidence DIR`.

## 6. Name shadowing

Two bundles sharing the same `name` in one lockfile is **shadowing** — the precondition for
attack primitive 1 (silent override). A conforming `lock` MUST fail (non-zero exit) when
shadowing is detected, and MAY offer an explicit override flag for the rare legitimate case.

## 7. What this spec deliberately does not do

- **No scanning.** Detection of malicious content is a separate layer (see `skillguard`,
  which emits SARIF). A lockfile proves *stability*, not *benignity*.
- **No trust decisions.** Pins say "this is what was reviewed", not "this is safe".
- **No distribution.** Registry protocols, discovery, and signing services build on top;
  `source` and `attestations` are their extension points.

## 8. Security considerations

- Hash pinning detects drift after trust was granted; initial trust remains a human or
  scanning-layer decision (TOFU — trust on first use — is the honest default).
- SHA-256 is used for ubiquity; tools MAY record additional digests in reserved fields.
- Lockfiles SHOULD be committed to version control so that drift is reviewed in code review.
- **`source` is provenance, not integrity.** The `source` fields are not covered by
  `tree_hash` (which spans `files` alone): a tampered lockfile can redirect a future update
  while every content hash still verifies. The mitigation is the boring one — commit
  lockfiles to version control and review lockfile diffs — and a change to `source.resolved`
  or `source.declared` MUST be treated as a security-relevant diff, not bookkeeping. This
  limitation is stated here rather than fixed here; fixing it requires signing (see
  `attestations`).

## 9. Reference implementation

`skilllock` (this repository) implements draft-03: `lock`, `verify`, `update`. The test
corpus enforces the semantics of sections 3–6 (37 behavior tests), including the
update-fetch rule as a structural property: `resolve_update_source()` can only ever return
URLs from the pinned entry, so a bundle's own content cannot feed the fetch decision.

## 10. Prior art and evidence

- Orca Security, "Skill Issues: Supply Chain Attack Vectors in an AI Agent Skills
  Marketplace" (2026) — primitives 1–4.
- Snyk, "ToxicSkills" (2026) — 36% prompt-injection rate in tested skills.
- Vercel `skills` CLI issue #283 — community demand for lockfile-driven install/sync.
- npm `package-lock.json`, Cargo `Cargo.lock`, Go `go.sum` — the dependency-pinning lineage.

## Appendix A. Interoperability mapping

The ecosystem has three provenance-shaped records. They map by meaning, not by value;
hashes from different algorithms are never interchangeable.

| skills-lock.json | Vercel `skills` CLI | SKILL.md frontmatter (#564) | Notes |
|---|---|---|---|
| `source.resolved` | `sourceUrl` | — | exact fetch URL; tool-written receipt |
| `source.declared` | — | `metadata.source` | author's claim, mirrored verbatim |
| `source.type` | `sourceType` | — | derived from `resolved`, never authored |
| `tree_hash` | `skillFolderHash` | — | structural counterpart only: different algorithm and input set; digests do **not** verify against each other |
| `files.*` | — | — | per-file pinning has no counterpart here; this granularity is the point of this spec |
| `name`, `version` | — | `name`, `metadata.version` | frontmatter-derived in both formats |

### A.1 The `metadata.source` frontmatter key (discussion #564)

An author MAY declare an origin in `SKILL.md` frontmatter (`metadata.source`), in either the
nested `metadata:` block form or the flat `metadata.source:` form. It answers "where did
the author say this came from?" for humans and for installers — and it is deliberately not
an authority: tools SHOULD copy it into `source.declared` at lock time and refresh it on
re-pin (it is a claim; keeping it stale serves nobody), but all fetch and trust decisions
use the lockfile (section 5.1). This is the same division npm settled on: the manifest may
suggest, the lock records.
