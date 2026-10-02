"""Lockfile core: bundle discovery, content hashing, verify statuses, per-skill update.

Draft-02 semantics (failure-visibility review): reasons are payloads (every non-verified
entry carries machine-readable evidence), localization is digest-only, and updates are
fail-closed (old pins survive any failure; new pins are re-hashed before commit).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

LOCK_VERSION = 1
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".cache"}
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---", re.DOTALL)


class LockError(Exception):
    pass


@dataclass
class SkillStatus:
    rel: str
    status: str  # verified | modified | missing | untracked | unverified-source
    changed_files: list = field(default_factory=list)  # paths only (compat)
    reason: dict = field(default_factory=dict)  # machine-readable evidence


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _bundle_files(bundle: Path) -> dict[str, str]:
    files = {}
    for path in sorted(bundle.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(bundle).parts):
            continue
        files[path.relative_to(bundle).as_posix()] = _sha256(path.read_bytes())
    return files


def _tree_hash(files: dict[str, str]) -> str:
    payload = "".join(f"{name}\0{digest}\n" for name, digest in sorted(files.items()))
    return _sha256(payload.encode("utf-8"))


def _frontmatter(bundle: Path) -> dict:
    text = (bundle / "SKILL.md").read_text(encoding="utf-8", errors="replace")
    match = FRONTMATTER_RE.match(text)
    meta = {}
    if match:
        for line in match.group(1).splitlines():
            m = re.match(r"^(name|version):\s*(.+?)\s*$", line)
            if m:
                meta[m.group(1)] = m.group(2).strip().strip("\"'")
    block = match.group(1) if match else ""
    # #564 metadata.source: the author's claimed origin (a hint, not authority).
    # Tolerate both the metadata: block form and the flat key form; the lockfile
    # is authoritative and this value is only mirrored into source.declared.
    flat = re.search(r"^metadata\.source\s*:\s*(\S+)\s*$", block, re.MULTILINE)
    if flat:
        meta["source"] = flat.group(1)
    else:
        nested = re.search(r"^metadata:\s*\n((?:[ \t]+\S.*\n?)*)", block, re.MULTILINE)
        if nested:
            inner = nested.group(1)
            source = re.search(r"^[ \t]+source\s*:\s*(\S+)\s*$", inner, re.MULTILINE)
            if source:
                meta["source"] = source.group(1)
            version = re.search(r"^[ \t]+version\s*:\s*(\S+)\s*$", inner, re.MULTILINE)
            if version and "version" not in meta:
                meta["version"] = version.group(1).strip().strip("\"'")
    return meta


def _discover(root: Path) -> dict[str, Path]:
    bundles = {}
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in SKIP_DIRS for part in skill_md.relative_to(root).parts):
            continue
        bundle = skill_md.parent
        bundles[bundle.relative_to(root).as_posix()] = bundle
    return bundles


def _derive_type(resolved: str | None) -> str:
    """Derive source type from the URL, never authored (agentskills #564)."""
    if not resolved:
        return "local"
    return "git" if resolved.endswith(".git") else "url"


def _entry_for(rel: str, bundle: Path, source: dict | None = None) -> dict:
    meta = _frontmatter(bundle)
    files = _bundle_files(bundle)
    resolved = (source or {}).get("resolved")
    return {
        "name": meta.get("name", bundle.name),
        "version": meta.get("version"),
        "source": {
            "type": (source or {}).get("type") or _derive_type(resolved),
            "resolved": resolved,
            "declared": meta.get("source"),
        },
        "files": files,
        "tree_hash": _tree_hash(files),
    }


def resolve_update_source(entry: dict) -> tuple[str | None, str | None]:
    """The only fetch sources an update may use: the pinned entry itself.

    Returns ("resolved", url) for a tool-recorded receipt, ("declared", url) for
    the one-shot author-claim fallback (#564 manual installs), or (None, None).
    URLs found in bundle content are deliberately unreachable from here, so a
    modified skill can never redirect its own update (update-hijack).
    """
    source = entry.get("source") or {}
    resolved = source.get("resolved")
    if resolved:
        return "resolved", resolved
    declared = source.get("declared")
    if declared:
        return "declared", declared
    return None, None


def _file_deltas(pinned: dict[str, str], current: dict[str, str]) -> list[dict]:
    """Digest-only localization (SPEC 4.2): names files from digest maps alone."""
    deltas = []
    for name in sorted(set(pinned) | set(current)):
        exp, act = pinned.get(name), current.get(name)
        if exp == act:
            continue
        kind = "added" if exp is None else "removed" if act is None else "modified"
        deltas.append({"path": name, "kind": kind, "expected": exp, "actual": act})
    return deltas


def lock_root(root: Path, allow_shadow: bool = False, source: dict | None = None) -> dict:
    root = Path(root)
    if not root.is_dir():
        raise LockError(f"not a directory: {root}")
    skills = {}
    names_seen: dict[str, list[str]] = {}
    for rel, bundle in _discover(root).items():
        skills[rel] = _entry_for(rel, bundle, source=source)
        names_seen.setdefault(skills[rel]["name"], []).append(rel)
    shadowed = {n: rels for n, rels in names_seen.items() if len(rels) > 1}
    if shadowed and not allow_shadow:
        detail = "; ".join(f"{n} -> {rels}" for n, rels in sorted(shadowed.items()))
        raise LockError(f"skill name shadowing detected: {detail}")
    return {"version": LOCK_VERSION, "generated_by": "skilllock", "skills": skills}


def verify(root: Path, lock: dict) -> list[SkillStatus]:
    root = Path(root)
    on_disk = _discover(root)
    statuses: list[SkillStatus] = []
    for rel, entry in sorted(lock.get("skills", {}).items()):
        bundle = on_disk.get(rel)
        if bundle is None:
            statuses.append(SkillStatus(rel, "missing", reason={
                "expected": entry.get("tree_hash"),
                "searched": [str(root / rel)],
            }))
            continue
        current = _bundle_files(bundle)
        pinned = entry.get("files", {})
        deltas = _file_deltas(pinned, current)
        if not deltas and _tree_hash(current) == entry.get("tree_hash"):
            statuses.append(SkillStatus(rel, "verified"))
        else:
            statuses.append(SkillStatus(
                rel, "modified",
                changed_files=[d["path"] for d in deltas],
                reason={"changed_files": deltas},
            ))
    for rel in sorted(set(on_disk) - set(lock.get("skills", {}))):
        statuses.append(SkillStatus(rel, "untracked", reason={"path": str(root / rel)}))
    return statuses


def update_skill(root: Path, lock: dict, name: str,
                 resolved_from: str | None = None) -> tuple[dict, dict]:
    root = Path(root)
    matches = [
        rel for rel, entry in lock.get("skills", {}).items()
        if entry.get("name") == name or rel == name
    ]
    if not matches:
        raise LockError(f"no pinned skill named {name!r}")
    if len(matches) > 1:
        raise LockError(f"name {name!r} is shadowed by bundles: {matches}")
    rel = matches[0]
    bundle = root / rel
    if not bundle.is_dir():
        raise LockError(f"bundle not on disk: {rel}")
    old = lock["skills"][rel]
    new_entry = _entry_for(rel, bundle)
    # Fail closed (SPEC 5): re-hash and compare before anything may be committed.
    recheck = _entry_for(rel, bundle)
    if recheck != new_entry:
        raise LockError(
            f"bundle {rel} drifted while updating; refusing to re-pin (old pins remain)"
        )
    # Source merge (SPEC 3): declared is refreshed from content (it is a claim),
    # resolved is a receipt -- kept unless the caller records where the new bytes
    # actually came from (the post-fallback step of the update-fetch rule).
    old_source = old.get("source") or {}
    built = new_entry["source"]
    if resolved_from:
        new_entry["source"] = {
            "type": built["type"],
            "resolved": resolved_from,
            "declared": built["declared"],
        }
    else:
        new_entry["source"] = {
            "type": old_source.get("type") or built["type"],
            "resolved": old_source.get("resolved"),
            "declared": built["declared"],
        }
    # Forward-compat preservation: unknown entry keys survive a re-pin untouched.
    for key, value in old.items():
        if key not in {"name", "version", "source", "files", "tree_hash"}:
            new_entry.setdefault(key, value)
    deltas = _file_deltas(old.get("files", {}), new_entry["files"])
    new_lock = {
        **lock,
        "skills": {**lock["skills"], rel: new_entry},
    }
    return new_lock, {rel: {
        "changed_files": [d["path"] for d in deltas],
        "locally_modified": bool(deltas),
    }}


def save_lock(path: Path, lock: dict) -> None:
    """Atomic replace (SPEC 5): write aside, then rename. Old pins survive any failure."""
    path = Path(path)
    tmp = path.parent / (path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(lock, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
