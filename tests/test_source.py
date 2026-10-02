"""Draft-03 behavior: source semantics, update-fetch rule, preservation on re-pin.

Driven by agentskills discussions #588 (Q1) and #564 (metadata.source fallback).

Interface under test:
    lock_root(root, allow_shadow=False, source=None) -> lock document
        source: optional {"resolved": url, "type": kind} recorded as fetch provenance
    update_skill(root, lock, name, resolved_from=None) -> (lock, changes summary)
    resolve_update_source(entry) -> (mode, url) | (None, None)
        mode: "resolved" (fetch here) | "declared" (one-shot fallback) | None (no fetch)

The security property under test: an update fetch may use ONLY the pinned lockfile
entry. URLs found in bundle content (a tampered SKILL.md, say) are never consulted,
so a modified skill cannot redirect its own update (update-hijack).
"""
from pathlib import Path

import pytest

from skilllock import (
    LockError,
    lock_root,
    resolve_update_source,
    update_skill,
    verify,
)

FRONTMATTER_BLOCK = """---
name: {name}
description: test skill
metadata:
  version: 2.1.0
  source: {source}
---
# {name}
"""

FRONTMATTER_FLAT = """---
name: {name}
description: test skill
metadata.source: {source}
---
# {name}
"""


def make_bundle(root: Path, rel: str, name: str, text: str | None = None):
    bundle = root / rel
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text(
        text or f"---\nname: {name}\ndescription: test skill\n---\n# {name}\n",
        encoding="utf-8",
    )
    return bundle


# --- lock: declared (author's claim) vs resolved (tool's receipt) --------------

def test_lock_records_declared_source_from_metadata_block(tmp_path):
    make_bundle(tmp_path, "cat/skill-a", "skill-a",
                FRONTMATTER_BLOCK.format(name="skill-a",
                                         source="https://github.com/owner/repo/tree/main/skills/skill-a"))
    entry = lock_root(tmp_path)["skills"]["cat/skill-a"]
    assert entry["source"] == {
        "type": "local",
        "resolved": None,
        "declared": "https://github.com/owner/repo/tree/main/skills/skill-a",
    }


def test_lock_records_declared_source_from_flat_metadata_key(tmp_path):
    make_bundle(tmp_path, "cat/skill-a", "skill-a",
                FRONTMATTER_FLAT.format(name="skill-a", source="https://example.com/skill-a"))
    entry = lock_root(tmp_path)["skills"]["cat/skill-a"]
    assert entry["source"]["declared"] == "https://example.com/skill-a"


def test_lock_without_source_info_records_local_origin(tmp_path):
    make_bundle(tmp_path, "cat/skill-a", "skill-a")
    entry = lock_root(tmp_path)["skills"]["cat/skill-a"]
    assert entry["source"] == {"type": "local", "resolved": None, "declared": None}


def test_lock_records_resolved_provenance_and_derives_type(tmp_path):
    make_bundle(tmp_path, "cat/skill-a", "skill-a")
    entry = lock_root(
        tmp_path,
        source={"resolved": "https://github.com/owner/repo.git"},
    )["skills"]["cat/skill-a"]
    assert entry["source"]["resolved"] == "https://github.com/owner/repo.git"
    assert entry["source"]["type"] == "git"  # derived from the URL, never authored


def test_lock_explicit_source_type_overrides_derivation(tmp_path):
    make_bundle(tmp_path, "cat/skill-a", "skill-a")
    entry = lock_root(
        tmp_path,
        source={"resolved": "https://mirror.example/skill-a.tgz", "type": "vendor"},
    )["skills"]["cat/skill-a"]
    assert entry["source"]["type"] == "vendor"


def test_declared_mismatch_with_resolved_is_not_an_error(tmp_path):
    make_bundle(tmp_path, "cat/skill-a", "skill-a",
                FRONTMATTER_BLOCK.format(name="skill-a",
                                         source="https://github.com/owner/repo/tree/main/skills/skill-a"))
    lock = lock_root(tmp_path, source={"resolved": "https://mirror.example/copy.tgz"})
    entry = lock["skills"]["cat/skill-a"]
    assert entry["source"]["declared"] != entry["source"]["resolved"]
    # legitimate (mirror/vendoring): verify must not fail over it
    assert all(s.status == "verified" for s in verify(tmp_path, lock))


# --- update-fetch rule: only the pinned entry may name a fetch URL -------------

def test_update_source_prefers_resolved_receipt_over_declared_claim():
    entry = {"source": {"type": "git", "resolved": "https://real.example/repo.git",
                        "declared": "https://claimed.example/repo"}}
    assert resolve_update_source(entry) == ("resolved", "https://real.example/repo.git")


def test_update_source_falls_back_to_pinned_declared_when_no_receipt():
    entry = {"source": {"type": "local", "resolved": None,
                        "declared": "https://github.com/owner/repo"}}
    assert resolve_update_source(entry) == ("declared", "https://github.com/owner/repo")


def test_update_source_none_when_entry_has_no_source(tmp_path):
    assert resolve_update_source({"name": "x", "source": None}) == (None, None)
    assert resolve_update_source({"name": "x"}) == (None, None)


def test_update_hijack_urls_in_bundle_content_are_never_used(tmp_path):
    """A tampered SKILL.md carrying an update URL must not redirect anything.

    The pin predates draft-03 (no source recorded). On-disk content now claims an
    evil origin. The fetch plan comes from the pinned entry only, so there is
    nothing to fetch from until an operator reviews and re-pins.
    """
    bundle = make_bundle(tmp_path, "cat/skill-a", "skill-a")
    lock = lock_root(tmp_path)
    lock["skills"]["cat/skill-a"].pop("source")  # pre-draft-03 pin
    evil = FRONTMATTER_BLOCK.format(name="skill-a", source="https://evil.example/update")
    bundle.joinpath("SKILL.md").write_text(evil, encoding="utf-8")
    assert resolve_update_source(lock["skills"]["cat/skill-a"]) == (None, None)


def test_update_fallback_then_records_actual_resolved(tmp_path):
    """#564 flow: manual install has only the author claim; after one update from
    it, the tool records where the bytes really came from and re-pins."""
    make_bundle(tmp_path, "cat/skill-a", "skill-a",
                FRONTMATTER_BLOCK.format(name="skill-a",
                                         source="https://github.com/owner/repo"))
    lock = lock_root(tmp_path)
    mode, url = resolve_update_source(lock["skills"]["cat/skill-a"])
    assert (mode, url) == ("declared", "https://github.com/owner/repo")
    (tmp_path / "cat/skill-a/SKILL.md").write_text(
        FRONTMATTER_BLOCK.format(name="skill-a", source="https://github.com/owner/repo")
        + "updated\n", encoding="utf-8")
    new_lock, changes = update_skill(tmp_path, lock, "skill-a",
                                     resolved_from="https://github.com/owner/repo.git")
    entry = new_lock["skills"]["cat/skill-a"]
    assert entry["source"]["resolved"] == "https://github.com/owner/repo.git"
    assert changes["cat/skill-a"]["locally_modified"] is True


# --- preservation and update summary ------------------------------------------

def test_update_preserves_unknown_entry_keys(tmp_path):
    make_bundle(tmp_path, "cat/skill-a", "skill-a")
    lock = lock_root(tmp_path)
    lock["skills"]["cat/skill-a"]["attestations"] = [{"sig": "sha256:abc"}]
    (tmp_path / "cat/skill-a/SKILL.md").write_text(
        "---\nname: skill-a\ndescription: test skill\n---\n# changed\n", encoding="utf-8")
    new_lock, _ = update_skill(tmp_path, lock, "skill-a")
    assert new_lock["skills"]["cat/skill-a"]["attestations"] == [{"sig": "sha256:abc"}]


def test_update_keeps_prior_resolved_unless_new_one_given(tmp_path):
    make_bundle(tmp_path, "cat/skill-a", "skill-a")
    lock = lock_root(tmp_path, source={"resolved": "https://github.com/owner/repo.git"})
    (tmp_path / "cat/skill-a/SKILL.md").write_text(
        "---\nname: skill-a\ndescription: test skill\n---\n# changed\n", encoding="utf-8")
    new_lock, _ = update_skill(tmp_path, lock, "skill-a")
    assert new_lock["skills"]["cat/skill-a"]["source"]["resolved"] == \
        "https://github.com/owner/repo.git"


def test_update_without_changes_reports_not_locally_modified(tmp_path):
    make_bundle(tmp_path, "cat/skill-a", "skill-a")
    lock = lock_root(tmp_path)
    _, changes = update_skill(tmp_path, lock, "skill-a")
    assert changes["cat/skill-a"]["locally_modified"] is False
