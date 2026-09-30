"""CLI tests for skilllock: lock/verify/update exit codes and lockfile output."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def make_bundle(root: Path, rel: str, name: str):
    bundle = root / rel
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test\n---\n# {name}\n", encoding="utf-8"
    )
    return bundle


def run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "skilllock", *args],
        capture_output=True, text=True, cwd=cwd or ROOT,
    )


def test_lock_then_verify_exits_zero(tmp_path):
    make_bundle(tmp_path, "c/skill-x", "skill-x")
    lockfile = tmp_path / "skills-lock.json"
    result = run("lock", str(tmp_path), "-o", str(lockfile))
    assert result.returncode == 0, result.stdout + result.stderr
    assert lockfile.exists()
    result = run("verify", str(tmp_path), "-l", str(lockfile))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "verified" in result.stdout


def test_verify_modified_exits_one(tmp_path):
    make_bundle(tmp_path, "c/skill-x", "skill-x")
    lockfile = tmp_path / "skills-lock.json"
    run("lock", str(tmp_path), "-o", str(lockfile))
    (tmp_path / "c/skill-x/SKILL.md").write_text("changed\n")
    result = run("verify", str(tmp_path), "-l", str(lockfile))
    assert result.returncode == 1
    assert "modified" in result.stdout


def test_lock_shadow_exits_nonzero(tmp_path):
    make_bundle(tmp_path, "x/skill-twin", "skill-twin")
    make_bundle(tmp_path, "y/skill-twin", "skill-twin")
    result = run("lock", str(tmp_path), "-o", str(tmp_path / "l.json"))
    assert result.returncode == 1
    assert "shadow" in (result.stdout + result.stderr).lower()


def test_update_named_skill_only(tmp_path):
    make_bundle(tmp_path, "c/skill-x", "skill-x")
    make_bundle(tmp_path, "c/skill-y", "skill-y")
    lockfile = tmp_path / "skills-lock.json"
    run("lock", str(tmp_path), "-o", str(lockfile))
    before = json.loads(lockfile.read_text())
    (tmp_path / "c/skill-x/SKILL.md").write_text("---\nname: skill-x\n---\nnew\n")
    (tmp_path / "c/skill-y/SKILL.md").write_text("---\nname: skill-y\n---\nnew\n")
    result = run("update", "skill-x", str(tmp_path), "-l", str(lockfile), "--yes")
    assert result.returncode == 0, result.stdout + result.stderr
    after = json.loads(lockfile.read_text())
    assert after["skills"]["c/skill-x"] != before["skills"]["c/skill-x"]
    assert after["skills"]["c/skill-y"] == before["skills"]["c/skill-y"]
