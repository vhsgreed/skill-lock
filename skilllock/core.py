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
    return meta


def _discover(root: Path) -> dict[str, Path]:
    bundles = {}
    for skill_md in sorted(root.rglob("SKILL.md")):
        if any(part in SKIP_DIRS for part in skill_md.relative_to(root).parts):
            continue
        bundle = skill_md.parent
        bundles[bundle.relative_to(root).as_posix()] = bundle
    return bundles


def _entry_for(rel: str, bundle: Path) -> dict:
    meta = _frontmatter(bundle)
    files = _bundle_files(bundle)
    return {
        "name": meta.get("name", bundle.name),
        "version": meta.get("version"),
        "files": files,
        "tree_hash": _tree_hash(files),
    }


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


def lock_root(root: Path, allow_shadow: bool = False) -> dict:
    root = Path(root)
    if not root.is_dir():
        raise LockError(f"not a directory: {root}")
    skills = {}
    names_seen: dict[str, list[str]] = {}
    for rel, bundle in _discover(root).items():
        skills[rel] = _entry_for(rel, bundle)
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


def update_skill(root: Path, lock: dict, name: str) -> tuple[dict, dict]:
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
    deltas = _file_deltas(old.get("files", {}), new_entry["files"])
    new_lock = {
        **lock,
        "skills": {**lock["skills"], rel: new_entry},
    }
    return new_lock, {rel: {"changed_files": [d["path"] for d in deltas]}}


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
