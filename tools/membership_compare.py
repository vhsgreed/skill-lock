"""Which files count as part of one skill directory, per tool?

Builds a small skill directory in a temp dir and lists the file set each tool
would hash. Reproduce with: python tools/membership_compare.py

- skill-lock: the real implementation (skilllock.core._bundle_files).
- vercel-labs/skills: re-implementation of collectFiles() in src/local-lock.ts
  (computeSkillFolderHash): skips directories named .git and node_modules,
  keeps Dirent.isFile() entries only, so symlinks are skipped.
- SkillRepo CLI: re-implementation of the rules its founder described in
  agentskills discussion #588 (2026-10-16): skips any path starting with '.',
  node_modules, and anything that is not a regular file.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from skilllock import core  # noqa: E402


def build(root: Path) -> Path:
    skill = root / "demo"
    for d in ("scripts", "references", "__pycache__", ".github", "node_modules/x"):
        (skill / d).mkdir(parents=True)
    (root / "outside").mkdir()
    files = {
        "SKILL.md": "---\nname: demo\ndescription: d\n---\nbody\n",
        "scripts/run.py": "print(1)\n",
        "references/REF.md": "ref\n",
        "__pycache__/run.cpython-314.pyc": "bytecode\n",
        ".github/ci.yml": "ci\n",
        ".env": "SECRET=1\n",
        "node_modules/x/index.js": "dep\n",
    }
    for rel, text in files.items():
        (skill / rel).write_text(text)
    (root / "outside" / "shared.md").write_text("shared\n")
    (skill / "references" / "shared.md").symlink_to("../../outside/shared.md")
    return skill


def vercel(base, cur, out):
    for e in os.scandir(cur):
        if e.is_dir(follow_symlinks=False):
            if e.name in (".git", "node_modules"):
                continue
            vercel(base, e.path, out)
        elif e.is_file(follow_symlinks=False):
            out.append(Path(os.path.relpath(e.path, base)).as_posix())


def skillrepo(base, cur, out):
    for e in os.scandir(cur):
        if e.name.startswith(".") or e.name == "node_modules":
            continue
        if e.is_dir(follow_symlinks=False):
            skillrepo(base, e.path, out)
        elif e.is_file(follow_symlinks=False):
            out.append(Path(os.path.relpath(e.path, base)).as_posix())


def main():
    with tempfile.TemporaryDirectory() as tmp:
        skill = build(Path(tmp))
        sets = {"skill-lock": sorted(core._bundle_files(skill))}
        v, s = [], []
        vercel(skill, skill, v)
        skillrepo(skill, skill, s)
        sets["vercel"], sets["skillrepo"] = sorted(v), sorted(s)
        paths = sorted(set().union(*sets.values()) | {"node_modules/x/index.js"})
        print(f"| file | {' | '.join(sets)} |")
        print("|---|" + "---|" * len(sets))
        for p in paths:
            note = " (symlink)" if p == "references/shared.md" else ""
            print(f"| `{p}`{note} | " + " | ".join("yes" if p in v_ else "no" for v_ in sets.values()) + " |")
        print("\nfile count:", {k: len(v_) for k, v_ in sets.items()})


if __name__ == "__main__":
    main()
