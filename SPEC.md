# skills-lock.json — Open Specification (draft-01)

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
      "source": null,
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
- `source` is reserved for provenance (registry URL, git remote); null in draft-01.
- `attestations` is reserved for signature envelopes (e.g. Sigstore, `skill.sig`);
  implementations MUST accept and preserve unknown entries here (forward compatibility).

Unknown top-level and per-skill fields MUST be preserved by tools that rewrite a lockfile.

## 4. Status model (`verify`)

For each pin in the lockfile and each bundle on disk:

| Status | Meaning |
|---|---|
| `verified` | bundle on disk hashes exactly to its pin |
| `modified` | bundle exists but files or hashes differ; the tool MUST list changed file paths (added, removed, or content-changed) |
| `missing` | pinned bundle absent from disk |
| `untracked` | bundle on disk with no pin |

`verify` succeeds (exit 0) only if every status is `verified`.

## 5. Update semantics (`update`)

A conforming tool MUST NOT provide a bulk update without an explicit bulk flag. The default
unit of update is **one named skill**:

1. Re-hash only the named bundle.
2. Present the changed-file list to the operator (the review step). In non-interactive use,
   writing the new pin requires an explicit confirmation flag.
3. Rewrite only that bundle's pin; every other pin MUST remain byte-identical.

This directly removes attack primitive 2 (blind bulk updates): a skill that turns malicious
on update surfaces as a per-skill change that must be reviewed and accepted.

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

## 9. Reference implementation

`skilllock` (this repository) implements draft-01: `lock`, `verify`, `update`. The test
corpus enforces the semantics of sections 4–6.

## 10. Prior art and evidence

- Orca Security, "Skill Issues: Supply Chain Attack Vectors in an AI Agent Skills
  Marketplace" (2026) — primitives 1–4.
- Snyk, "ToxicSkills" (2026) — 36% prompt-injection rate in tested skills.
- Vercel `skills` CLI issue #283 — community demand for lockfile-driven install/sync.
- npm `package-lock.json`, Cargo `Cargo.lock`, Go `go.sum` — the dependency-pinning lineage.
