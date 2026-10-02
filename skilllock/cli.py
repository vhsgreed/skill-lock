"""CLI for skilllock: lock, verify, per-skill update with review summary."""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from .core import LockError, lock_root, save_lock, update_skill, verify


def _write_evidence(evidence_dir, command: str, payload: dict) -> None:
    """Per-attempt evidence (SPEC 5.1): distinct file per run, never truncate."""
    directory = Path(evidence_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{command}-{time.time_ns()}.json"
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="skilllock")
    sub = parser.add_subparsers(dest="command")

    p_lock = sub.add_parser("lock", help="pin every skill bundle under ROOT")
    p_lock.add_argument("root")
    p_lock.add_argument("-o", "--output", default="skills-lock.json")
    p_lock.add_argument("--allow-shadow", action="store_true",
                        help="permit duplicate skill names (dangerous: enables silent override)")
    p_lock.add_argument("--source-url", default=None,
                        help="record where these bytes were actually fetched from (source.resolved)")
    p_lock.add_argument("--source-type", default=None,
                        help="override the derived source type (git | url | registry | vendor | local)")

    p_verify = sub.add_parser("verify", help="compare installed bundles against the lockfile")
    p_verify.add_argument("root")
    p_verify.add_argument("-l", "--lock", default="skills-lock.json")
    p_verify.add_argument("--evidence", default=None,
                          help="write the raw result payload to a per-attempt file in DIR")

    p_update = sub.add_parser("update", help="re-pin ONE skill after reviewing its changes")
    p_update.add_argument("name")
    p_update.add_argument("root")
    p_update.add_argument("-l", "--lock", default="skills-lock.json")
    p_update.add_argument("--yes", action="store_true", help="write the new lockfile entry")
    p_update.add_argument("--resolved-from", default=None,
                          help="record where the new bytes really came from (post-fallback receipt)")
    p_update.add_argument("--evidence", default=None,
                          help="write the raw result payload to a per-attempt file in DIR")

    args = parser.parse_args(argv)
    try:
        if args.command == "lock":
            source = None
            if args.source_url or args.source_type:
                source = {"resolved": args.source_url, "type": args.source_type}
            lock = lock_root(Path(args.root), allow_shadow=args.allow_shadow,
                             source=source)
            save_lock(Path(args.output), lock)
            print(f"skilllock: pinned {len(lock['skills'])} skill(s) -> {args.output}")
            return 0

        if args.command == "verify":
            lock_path = Path(args.lock)
            if not lock_path.exists():
                print(f"skilllock: lockfile not found: {lock_path}", file=sys.stderr)
                return 2
            statuses = verify(Path(args.root), json.loads(lock_path.read_text()))
            if args.evidence:
                _write_evidence(args.evidence, "verify", {
                    "command": "verify", "root": args.root, "lock": args.lock,
                    "statuses": [asdict(s) for s in statuses],
                })
            for s in statuses:
                print(f"{s.status:<10} {s.rel}")
                if s.status == "modified":
                    for d in s.reason.get("changed_files", []):
                        print(f"             ~ {d['path']} [{d['kind']}] "
                              f"{(d['expected'] or 'none')[:15]} -> {(d['actual'] or 'none')[:15]}")
                elif s.status == "missing":
                    print(f"             expected tree {str(s.reason.get('expected'))[:22]}")
                    for p in s.reason.get("searched", []):
                        print(f"             searched: {p}")
                elif s.status == "untracked":
                    print(f"             at {s.reason.get('path')}")
            ok = all(s.status == "verified" for s in statuses)
            print(f"skilllock: {sum(s.status == 'verified' for s in statuses)}/{len(statuses)} verified")
            return 0 if ok else 1

        if args.command == "update":
            lock_path = Path(args.lock)
            if not lock_path.exists():
                print(f"skilllock: lockfile not found: {lock_path}", file=sys.stderr)
                return 2
            lock = json.loads(lock_path.read_text())
            new_lock, changes = update_skill(Path(args.root), lock, args.name,
                                            resolved_from=args.resolved_from)
            if args.evidence:
                _write_evidence(args.evidence, "update", {
                    "command": "update", "name": args.name,
                    "root": args.root, "lock": args.lock,
                    "changes": changes, "written": bool(args.yes),
                })
            for rel, info in changes.items():
                print(f"changes in {rel}:")
                for f in info["changed_files"]:
                    print(f"  ~ {f}")
                if not info["changed_files"]:
                    print("  (no content changes)")
            if not args.yes:
                print("skilllock: review the changes above; re-run with --yes to re-pin")
                return 0
            save_lock(lock_path, new_lock)
            print(f"skilllock: re-pinned {args.name}")
            return 0
    except LockError as exc:
        print(f"skilllock: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
