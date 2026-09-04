"""
Standalone alembic revision-chain checker.

Run from the repo root:  python check_alembic_chain.py
No DB connection needed -- this only parses alembic/versions/*.py and
walks the revision/down_revision graph, so it's safe to run before you've
even applied the new migrations locally.

Reports:
  1. Every revision and what it points to (down_revision).
  2. Any down_revision that references a file that doesn't exist anymore
     (this is exactly what deleting a migration file breaks).
  3. Multiple heads (more than one revision that nothing points to as a
     parent) -- alembic will refuse `upgrade head` until these are merged.
  4. The linear chain from base -> head(s), so you can eyeball it against
     what you expect after the merge.
"""

import ast
import sys
from pathlib import Path

VERSIONS_DIR = Path("alembic/versions")


def _extract_revision_vars(path: Path):
    """Pull `revision` and `down_revision` without importing the module
    (these files import `alembic.op`, which may not be installed/configured
    in every environment this check runs in)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    revision = None
    down_revision = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
            if "revision" in targets and "down_revision" not in targets:
                if isinstance(value, ast.Constant):
                    revision = value.value
            if "down_revision" in targets:
                if isinstance(value, ast.Constant):
                    down_revision = value.value
                elif isinstance(value, (ast.Tuple, ast.List)):
                    down_revision = tuple(
                        elt.value for elt in value.elts if isinstance(elt, ast.Constant)
                    )
                # ast.Constant with value None covers `down_revision = None`
    return revision, down_revision


def main():
    if not VERSIONS_DIR.exists():
        print(f"ERROR: {VERSIONS_DIR} not found. Run this from the repo root.")
        sys.exit(1)

    files = sorted(VERSIONS_DIR.glob("*.py"))
    revisions = {}  # revision_id -> (down_revision, filename)

    for f in files:
        try:
            rev, down = _extract_revision_vars(f)
        except SyntaxError as exc:
            print(f"WARNING: could not parse {f.name}: {exc}")
            continue
        if rev is None:
            continue
        revisions[rev] = (down, f.name)

    print(f"Found {len(revisions)} migration files.\n")

    # 1. Dangling down_revision references (deleted/renamed parent files)
    all_ids = set(revisions.keys())
    dangling = []
    for rev, (down, fname) in revisions.items():
        downs = down if isinstance(down, tuple) else (down,)
        for d in downs:
            if d is not None and d not in all_ids:
                dangling.append((rev, fname, d))

    if dangling:
        print("BROKEN CHAIN -- these revisions point to a down_revision")
        print("that doesn't exist in alembic/versions/ anymore:\n")
        for rev, fname, missing in dangling:
            print(f"  {fname}")
            print(f"    revision      = {rev!r}")
            print(f"    down_revision = {missing!r}  <-- NOT FOUND")
        print()
        print("This is exactly what happens when a migration file is deleted")
        print("(like 3e2b6ce6147f_merge_migration_heads.py) without repointing")
        print("every file whose down_revision referenced it. Fix by editing the")
        print("down_revision above to the correct new parent before you push.\n")
    else:
        print("OK: every down_revision resolves to a file that exists.\n")

    # 2. Multiple heads: revisions that no other revision lists as a parent
    referenced_as_parent = set()
    for down, _ in revisions.values():
        downs = down if isinstance(down, tuple) else (down,)
        referenced_as_parent.update(d for d in downs if d is not None)

    heads = [rev for rev in revisions if rev not in referenced_as_parent]

    if len(heads) > 1:
        print(f"MULTIPLE HEADS DETECTED ({len(heads)}) -- alembic upgrade will")
        print("fail until these are merged with `alembic merge heads`:\n")
        for h in heads:
            print(f"  {h}  ({revisions[h][1]})")
        print()
    elif len(heads) == 1:
        print(f"OK: single head -> {heads[0]}  ({revisions[heads[0]][1]})\n")
    else:
        print("ERROR: no head found at all (empty or fully cyclic graph?).\n")

    # 3. Print the chain(s) root -> tip for a visual sanity check
    print("Chain(s) from base to tip:")
    children_of = {}
    for rev, (down, _) in revisions.items():
        downs = down if isinstance(down, tuple) else (down,)
        for d in downs:
            children_of.setdefault(d, []).append(rev)

    roots = [r for r, (down, _) in revisions.items() if down is None]
    for root in roots:
        chain = [root]
        current = root
        while True:
            nxts = children_of.get(current, [])
            if len(nxts) == 0:
                break
            if len(nxts) > 1:
                chain.append(f"  <-- FORK: {nxts}")
                break
            current = nxts[0]
            chain.append(current)
        print("  " + " -> ".join(str(c) for c in chain))
        print()


if __name__ == "__main__":
    main()