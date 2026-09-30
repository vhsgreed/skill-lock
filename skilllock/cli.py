"""CLI for skilllock: lock, verify, per-skill update with review summary."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import LockError, lock_root, update_skill, verify


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="skilllock")
    sub = parser.add_subparsers(dest="command")

    p_lock = sub.add_parser("lock", help="pin every skill bundle under ROOT")
    p_lock.add_argument("root")
    p_lock.add_argument("-o", "--output", default="skills-lock.json")
    p_lock.add_argument("--allow-shadow", action="store_true",
                        help="permit duplicate skill names (dangerous: enables silent override)")

    p_verify = sub.add_parser("verify", help="compare installed bundles against the lockfile")
    p_verify.add_argument("root")
    p_verify.add_argument("-l", "--lock", default="skills-lock.json")

    p_update = sub.add_parser("update", help="re-pin ONE skill after reviewing its changes")
    p_update.add_argument("name")
    p_update.add_argument("root")
    p_update.add_argument("-l", "--lock", default="skills-lock.json")
    p_update.add_argument("--yes", action="store_true", help="write the new lockfile entry")

    args = parser.parse_args(argv)
    try:
        if args.command == "lock":
            lock = lock_root(Path(args.root), allow_shadow=args.allow_shadow)
            Path(args.output).write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
            print(f"skilllock: pinned {len(lock['skills'])} skill(s) -> {args.output}")
            return 0

        if args.command == "verify":
            lock_path = Path(args.lock)
            if not lock_path.exists():
                print(f"skilllock: lockfile not found: {lock_path}", file=sys.stderr)
                return 2
            statuses = verify(Path(args.root), json.loads(lock_path.read_text()))
            for s in statuses:
                extra = f"  changed: {', '.join(s.changed_files)}" if s.changed_files else ""
                print(f"{s.status:<10} {s.rel}{extra}")
            ok = all(s.status == "verified" for s in statuses)
            print(f"skilllock: {sum(s.status == 'verified' for s in statuses)}/{len(statuses)} verified")
            return 0 if ok else 1

        if args.command == "update":
            lock_path = Path(args.lock)
            if not lock_path.exists():
                print(f"skilllock: lockfile not found: {lock_path}", file=sys.stderr)
                return 2
            lock = json.loads(lock_path.read_text())
            new_lock, changes = update_skill(Path(args.root), lock, args.name)
            for rel, info in changes.items():
                print(f"changes in {rel}:")
                for f in info["changed_files"]:
                    print(f"  ~ {f}")
                if not info["changed_files"]:
                    print("  (no content changes)")
            if not args.yes:
                print("skilllock: review the changes above; re-run with --yes to re-pin")
                return 0
            lock_path.write_text(json.dumps(new_lock, indent=2) + "\n", encoding="utf-8")
            print(f"skilllock: re-pinned {args.name}")
            return 0
    except LockError as exc:
        print(f"skilllock: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
