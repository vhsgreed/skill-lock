# skill-lock

Vendor-neutral **hash pinning and update control for agent skills** — the
`package-lock.json` for `SKILL.md` bundles. Reference implementation of
[`SPEC.md`](SPEC.md) (draft-01).

Attackers can silently override installed skills, and skill registries bulk-update without
review — demonstrated supply-chain primitives in the 2026 agent-skills ecosystem (Orca
Security). skill-lock closes exactly those two gaps:

- **pin** every file of every skill bundle (SHA-256 + tree hash),
- **verify** drift with named statuses (`verified` / `modified` / `missing` / `untracked`),
- **update one skill at a time**, with a review step before the pin is rewritten,
- **fail on name shadowing** (the silent-override precondition).

Detection of *malicious content* is a separate layer: use
[`skillguard`](../skillguard) for scanning (SARIF), this tool for stability.

## Install

```bash
pip install .     # stdlib only, Python >= 3.10
```

## Usage

```bash
skilllock lock ~/.hermes/skills -o skills-lock.json   # pin everything
skilllock verify ~/.hermes/skills -l skills-lock.json # exit 1 on any drift
skilllock update <skill-name> ~/.hermes/skills -l skills-lock.json         # review changes
skilllock update <skill-name> ~/.hermes/skills -l skills-lock.json --yes   # accept re-pin
```

Commit `skills-lock.json` to version control so drift is reviewed in code review.

## Verified behavior (dogfooded on 58 live skills)

```
skilllock: pinned 58 skill(s) -> skills-lock.json
skilllock: 58/58 verified
--- tamper a file ---
modified   xurl  changed: SKILL.md
skilllock: 0/1 verified        (exit 1)
--- skilllock update xurl ---
changes in xurl:
  ~ SKILL.md
skilllock: review the changes above; re-run with --yes to re-pin
```

The `tests/` corpus enforces the spec semantics: content-sensitive tree hashes, all four
verify statuses, shadowing failure, and per-skill update leaving every other pin
byte-identical.

## Design notes

- **Trust model:** TOFU. A pin says "this is what was reviewed", not "this is safe" — pair
  with `skillguard` scans at lock time.
- **Extensibility:** `source` and `attestations` fields are reserved by the spec for
  provenance and signature envelopes (Sigstore / `skill.sig`); unknown fields are preserved.
- **Runtime-agnostic:** keys are relative bundle paths; works for Hermes, Claude Code,
  OpenClaw, Codex — any tool that reads `SKILL.md` bundles.

MIT license.
