"""Draft-02 behavior: reason payloads, digest-only localization, fail-closed updates.

Driven by the failure-visibility review on agentskills discussion #588:
a status is not a diagnosis; every non-verified entry carries a machine-readable reason,
localization comes only from digest comparison, and a failed update leaves old pins intact.
"""
import json
import os
from pathlib import Path

import pytest

from skilllock import LockError, lock_root, update_skill, verify


def make_bundle(root: Path, rel: str, name: str, files: dict | None = None):
    bundle = root / rel
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text(
        f"---\nname: {name}\nversion: 1.0.0\n---\n# {name}\n", encoding="utf-8"
    )
    for relpath, content in (files or {}).items():
        target = bundle / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return bundle


@pytest.fixture
def root(tmp_path):
    make_bundle(tmp_path, "cat-a/skill-a", "skill-a",
                files={"references/notes.md": "notes\n",
                       "references/scary.md": "WARNING: rm -rf / is dangerous\n"})
    return tmp_path


# --- reason payloads ---------------------------------------------------------

def test_missing_reason_carries_searched_path_and_expected_tree_hash(root):
    lock = lock_root(root)
    expected_tree = lock["skills"]["cat-a/skill-a"]["tree_hash"]
    (root / "cat-a/skill-a/SKILL.md").unlink()
    (root / "cat-a/skill-a/references/notes.md").unlink()
    (root / "cat-a/skill-a/references/scary.md").unlink()
    (root / "cat-a/skill-a/references").rmdir()
    (root / "cat-a/skill-a").rmdir()
    st = verify(root, lock)[0]
    assert st.status == "missing"
    assert st.reason["expected"] == expected_tree
    assert any(str(p).endswith("cat-a/skill-a") for p in st.reason["searched"])


def test_modified_reason_has_per_file_delta_with_expected_and_actual_digests(root):
    lock = lock_root(root)
    (root / "cat-a/skill-a/references/notes.md").write_text("tampered\n")
    st = verify(root, lock)[0]
    assert st.status == "modified"
    deltas = {d["path"]: d for d in st.reason["changed_files"]}
    assert deltas["references/notes.md"]["kind"] == "modified"
    pinned = lock["skills"]["cat-a/skill-a"]["files"]["references/notes.md"]
    assert deltas["references/notes.md"]["expected"] == pinned
    assert deltas["references/notes.md"]["actual"].startswith("sha256:")
    assert deltas["references/notes.md"]["actual"] != pinned


def test_added_file_delta_kind_added(root):
    lock = lock_root(root)
    (root / "cat-a/skill-a/new.sh").write_text("echo hi\n")
    st = verify(root, lock)[0]
    deltas = {d["path"]: d for d in st.reason["changed_files"]}
    assert deltas["new.sh"]["kind"] == "added"
    assert deltas["new.sh"]["expected"] is None
    assert deltas["new.sh"]["actual"].startswith("sha256:")


def test_removed_file_delta_kind_removed(root):
    lock = lock_root(root)
    (root / "cat-a/skill-a/references/scary.md").unlink()
    st = verify(root, lock)[0]
    deltas = {d["path"]: d for d in st.reason["changed_files"]}
    assert deltas["references/scary.md"]["kind"] == "removed"
    assert deltas["references/scary.md"]["actual"] is None


# --- digest-only localization (the false-green/false-red rule) ----------------

def test_localization_names_only_the_digest_changed_file(root):
    """The scary-text file must NOT be blamed when its bytes did not change."""
    lock = lock_root(root)
    (root / "cat-a/skill-a/references/notes.md").write_text("benign edit\n")
    st = verify(root, lock)[0]
    assert st.changed_files == ["references/notes.md"]
    assert "references/scary.md" not in st.changed_files


# --- fail-closed update ------------------------------------------------------

def test_failed_update_leaves_lockfile_untouched(root, monkeypatch):
    """If the bundle drifts mid-update (re-hash disagrees), the CLI writes nothing."""
    import skilllock.cli as cli
    import skilllock.core as core

    lockfile = root / "skills-lock.json"
    lock_root(root)  # ensure bundle exists before we fingerprint the file
    lockfile.write_text(json.dumps(lock_root(root)) + "  \n")  # trailing spaces = fingerprint
    before = lockfile.read_bytes()

    real_entry_for = core._entry_for
    calls = {"n": 0}

    def drifting_entry_for(rel, bundle):
        calls["n"] += 1
        entry = real_entry_for(rel, bundle)
        if calls["n"] > 1:  # the re-hash pass sees different content than the first
            entry = {**entry, "tree_hash": "sha256:" + "0" * 64}
        return entry

    monkeypatch.setattr(core, "_entry_for", drifting_entry_for)
    rc = cli.main(["update", "skill-a", str(root), "-l", str(lockfile), "--yes"])
    assert rc == 1
    assert lockfile.read_bytes() == before  # byte-identical, trailing spaces intact
    assert not [p for p in root.iterdir() if p.name.startswith("skills-lock.json.")]


def test_save_lock_is_atomic_and_repins_cleanly(root):
    from skilllock import save_lock

    lockfile = root / "skills-lock.json"
    lock_root(root)
    lockfile.write_text(json.dumps(lock_root(root), indent=2) + "\n")
    lock = json.loads(lockfile.read_text())
    (root / "cat-a/skill-a/SKILL.md").write_text("---\nname: skill-a\n---\n# v2\n")
    new_lock, changes = update_skill(root, lock, "skill-a")
    assert changes["cat-a/skill-a"]["changed_files"]
    save_lock(lockfile, new_lock)
    assert json.loads(lockfile.read_text())["skills"]["cat-a/skill-a"] == \
        new_lock["skills"]["cat-a/skill-a"]
    assert not [p for p in root.iterdir() if p.name.startswith("skills-lock.json.")]


# --- verified entries carry no requirement ------------------------------------

def test_verified_entry_reason_is_empty(root):
    lock = lock_root(root)
    st = verify(root, lock)[0]
    assert st.status == "verified"
    assert st.reason == {} or st.reason is None
