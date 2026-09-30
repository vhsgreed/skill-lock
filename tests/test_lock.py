"""Behavior tests for skill-lock: hash pinning, verify statuses, shadow detection,
per-skill updates.

Interface under test:
    from skilllock import lock_root, verify, update_skill, LockError
    lock_root(root: Path, allow_shadow=False) -> dict (lockfile document)
    verify(root: Path, lock: dict) -> list[SkillStatus]
    update_skill(root: Path, lock: dict, name: str) -> (dict, changes summary)
"""
import hashlib
import json
from pathlib import Path

import pytest

from skilllock import LockError, lock_root, update_skill, verify


def make_bundle(root: Path, rel: str, name: str, version: str = "1.0.0",
                files: dict | None = None):
    bundle = root / rel
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text(
        f"---\nname: {name}\nversion: {version}\ndescription: test skill\n---\n# {name}\n",
        encoding="utf-8",
    )
    for relpath, content in (files or {}).items():
        target = bundle / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return bundle


@pytest.fixture
def root(tmp_path):
    make_bundle(tmp_path, "cat-a/skill-a", "skill-a", files={"references/notes.md": "notes\n"})
    make_bundle(tmp_path, "cat-b/skill-b", "skill-b")
    return tmp_path


# --- lock --------------------------------------------------------------------

def test_lock_records_per_file_hashes_and_tree_hash(root):
    lock = lock_root(root)
    entry = lock["skills"]["cat-a/skill-a"]
    assert entry["name"] == "skill-a"
    assert entry["version"] == "1.0.0"
    assert set(entry["files"]) == {"SKILL.md", "references/notes.md"}
    for digest in entry["files"].values():
        assert digest.startswith("sha256:")
    assert entry["tree_hash"].startswith("sha256:")


def test_lock_tree_hash_is_deterministic_and_content_sensitive(root):
    a1 = lock_root(root)["skills"]["cat-a/skill-a"]["tree_hash"]
    a2 = lock_root(root)["skills"]["cat-a/skill-a"]["tree_hash"]
    assert a1 == a2
    (root / "cat-a/skill-a/references/notes.md").write_text("changed\n")
    a3 = lock_root(root)["skills"]["cat-a/skill-a"]["tree_hash"]
    assert a3 != a1


def test_lock_rejects_duplicate_skill_names_unless_allowed(tmp_path):
    make_bundle(tmp_path, "x/skill-twin", "skill-twin")
    make_bundle(tmp_path, "y/skill-twin", "skill-twin")
    with pytest.raises(LockError) as exc:
        lock_root(tmp_path)
    assert "skill-twin" in str(exc.value)
    lock = lock_root(tmp_path, allow_shadow=True)
    assert len(lock["skills"]) == 2


# --- verify ------------------------------------------------------------------

def test_verify_clean_tree_is_all_verified(root):
    lock = lock_root(root)
    statuses = verify(root, lock)
    assert {s.rel: s.status for s in statuses} == {
        "cat-a/skill-a": "verified",
        "cat-b/skill-b": "verified",
    }


def test_verify_detects_modified_file_by_name(root):
    lock = lock_root(root)
    (root / "cat-a/skill-a/references/notes.md").write_text("tampered\n")
    statuses = {s.rel: s for s in verify(root, lock)}
    st = statuses["cat-a/skill-a"]
    assert st.status == "modified"
    assert "references/notes.md" in st.changed_files
    assert statuses["cat-b/skill-b"].status == "verified"


def test_verify_detects_missing_bundle(root):
    lock = lock_root(root)
    (root / "cat-b/skill-b/SKILL.md").unlink()
    (root / "cat-b/skill-b").rmdir()
    statuses = {s.rel: s.status for s in verify(root, lock)}
    assert statuses["cat-b/skill-b"] == "missing"


def test_verify_detects_untracked_bundle(root):
    lock = lock_root(root)
    make_bundle(root, "cat-c/skill-c", "skill-c")
    statuses = {s.rel: s.status for s in verify(root, lock)}
    assert statuses["cat-c/skill-c"] == "untracked"


def test_verify_detects_added_file_in_tracked_bundle(root):
    lock = lock_root(root)
    (root / "cat-b/skill-b/extra.sh").write_text("echo hi\n")
    statuses = {s.rel: s for s in verify(root, lock)}
    assert statuses["cat-b/skill-b"].status == "modified"
    assert "extra.sh" in statuses["cat-b/skill-b"].changed_files


# --- per-skill update (anti 'blind bulk update') ------------------------------

def test_update_relocks_only_named_skill(root):
    lock = lock_root(root)
    (root / "cat-a/skill-a/SKILL.md").write_text("---\nname: skill-a\n---\n# changed\n")
    (root / "cat-b/skill-b/SKILL.md").write_text("---\nname: skill-b\n---\n# changed too\n")
    new_lock, changes = update_skill(root, lock, "skill-a")
    assert changes["cat-a/skill-a"]["changed_files"] == ["SKILL.md"]
    assert new_lock["skills"]["cat-a/skill-a"] != lock["skills"]["cat-a/skill-a"]
    # untouched skill keeps its exact pinned entry (byte-identical)
    assert new_lock["skills"]["cat-b/skill-b"] == lock["skills"]["cat-b/skill-b"]


def test_update_unknown_skill_raises(root):
    lock = lock_root(root)
    with pytest.raises(LockError):
        update_skill(root, lock, "no-such-skill")


def test_lockfile_round_trips_through_json(root):
    lock = lock_root(root)
    doc = json.loads(json.dumps(lock))
    assert verify(root, doc) and all(s.status == "verified" for s in verify(root, doc))
