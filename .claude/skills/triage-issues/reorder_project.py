#!/usr/bin/env python3
"""Order the aide-loop GitHub Project so the board reads in priority-of-attention
order: fair-game open issues first, then deferred ones, then Done. Optionally
retire long-Done items off the board.

The partition is *stable* — relative order inside each bucket is preserved —
because this tracker has no priority axis, and hand-sorting inside a bucket
would encode an ordering nothing else can read.

    python .claude/skills/triage-issues/reorder_project.py --dry-run
    python .claude/skills/triage-issues/reorder_project.py

    # keep every Done item on the board
    python .claude/skills/triage-issues/reorder_project.py --archive-after-days never

Retiring long-Done items is part of the default pass, governed by the one
`--archive-after-days` argument (a day count, or `never`). It is reversible
(`unarchiveProjectV2Item`) and hides the item from every view without touching
the issue — but it decides what the *next* triage can see, so run --dry-run
first and show the list.

Only the items that must move are moved: the longest run of the board already
in target order stays put, and every other item is placed once, after its
target predecessor. Rewriting all ~150 positions took over two minutes, one
`gh` spawn per item, when the typical pass needs a dozen moves.

Idempotent, and a fixpoint: a second run over an ordered board with nothing
newly stale issues no mutations, and an interrupted run is finished by
re-running it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import tomllib

PROJECT_ID = "PVT_kwHOByffxc4Bg9iM"
PROJECT_NUMBER = "1"
OWNER = "dadrobny"
#: Machine-local facts (the gh path when it is off PATH) sit next to this
#: script in a gitignored local.toml; local.toml.example holds the shape.
LOCAL_TOML = pathlib.Path(__file__).with_name("local.toml")

#: A Done item stays on the board for roughly the last few PR cycles, so the
#: un-defer sweep and the "did we just fix this?" check in triage step 2 can
#: still see it. Measured on 2026-09-01: at 7 days this retires 13 items,
#: among them #46, whose lint two still-open issues are about; at 30 it
#: retires none. A week is inside the window triage is still reading.
DEFAULT_ARCHIVE_AFTER_DAYS = 30

MOVE = """
mutation($p:ID!,$i:ID!,$a:ID){
  updateProjectV2ItemPosition(input:{projectId:$p, itemId:$i, afterId:$a}){
    clientMutationId } }
"""

ARCHIVE = """
mutation($p:ID!,$i:ID!){
  archiveProjectV2Item(input:{projectId:$p, itemId:$i}){ clientMutationId } }
"""

CLOSED_AT = """
query($login:String!,$number:Int!,$cursor:String){
  user(login:$login){ projectV2(number:$number){
    items(first:100, after:$cursor){
      pageInfo{ hasNextPage endCursor }
      nodes{ id content{
        __typename
        ... on Issue { closedAt }
        ... on PullRequest { closedAt } } } } } } }
"""


def find_gh() -> tuple[str, str]:
    """The gh binary and where it came from: local.toml's top-level `gh` key
    if set, else the bare name for PATH to resolve."""
    if LOCAL_TOML.is_file():
        try:
            with LOCAL_TOML.open("rb") as fh:
                data = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            sys.exit(f"{LOCAL_TOML}: cannot read: {exc}")
        if "gh" in data.get("consumers", {}):
            sys.exit(f"{LOCAL_TOML}: `gh` is a top-level key — move it above "
                     "the [consumers] header")
        configured = data.get("gh")
        if configured is not None:
            if not isinstance(configured, str) or not configured:
                sys.exit(f"{LOCAL_TOML}: `gh` must be a non-empty string path")
            return os.path.expanduser(configured), str(LOCAL_TOML)
    return "gh", "PATH"


GH_SOURCE = "PATH"   # set by main(); names where the gh path came from


def run(argv: list[str]) -> str:
    # encoding= rather than text=, so a non-UTF-8 default locale cannot mangle
    # an issue title (conventions.md §6, and issue #126).
    try:
        proc = subprocess.run(
            argv, capture_output=True, encoding="utf-8", errors="replace"
        )
    except OSError as exc:
        sys.exit(f"cannot run {argv[0]} (from {GH_SOURCE}): {exc}")
    if proc.returncode != 0:
        sys.exit(f"{argv[0]} failed ({proc.returncode}):\n{proc.stderr.strip()}")
    return proc.stdout


def graphql(gh: str, query: str, **variables: str) -> dict:
    argv = [gh, "api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        # -F coerces ints/nulls; -f would send them as strings.
        argv += ["-F", f"{key}={value}"]
    return json.loads(run(argv))


def closed_at_by_item(gh: str) -> dict[str, dt.datetime]:
    """Map project item id -> when its issue/PR was closed.

    `gh project item-list` does not carry a closed timestamp, and an item's
    Status can be flipped to Done by hand without the issue ever closing, so
    an item with no timestamp is simply never a retirement candidate.
    """
    found: dict[str, dt.datetime] = {}
    cursor = "null"
    while True:
        page = graphql(gh, CLOSED_AT, login=OWNER,
                       number=PROJECT_NUMBER, cursor=cursor)
        items = page["data"]["user"]["projectV2"]["items"]
        for node in items["nodes"]:
            stamp = (node.get("content") or {}).get("closedAt")
            if stamp:
                found[node["id"]] = dt.datetime.fromisoformat(stamp)
        if not items["pageInfo"]["hasNextPage"]:
            return found
        cursor = items["pageInfo"]["endCursor"]


def bucket(item: dict) -> int:
    """0 = fair game, 1 = deferred, 2 = done."""
    if (item.get("status") or "") == "Done":
        return 2
    return 1 if "deferred" in (item.get("labels") or []) else 0


def label(item: dict) -> str:
    """How one item prints in the `--dry-run` review surface.

    The title comes from the **content**, never the item. `gh project
    item-list` caches an item-level `title` that a later `gh issue edit` does
    not invalidate: #74 still printed the title it was filed under, months
    after being renamed. Since the dry-run printout is what a human reads
    before approving a reorder, a stale title there is a review of the wrong
    board. The item-level value stays as the fallback for a draft item, which
    has no issue behind it.
    """
    content = item.get("content") or {}
    number = content.get("number")
    head = f"#{number}" if number else "(draft)"
    title = content.get("title") or item.get("title") or ""
    return f"{head} {title[:58]}"


def archive_after(value: str) -> int | None:
    """A day count, or `never` to keep every Done item on the board."""
    if value.strip().lower() == "never":
        return None
    try:
        days = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected a number of days or 'never', got {value!r}") from None
    if days < 0:
        raise argparse.ArgumentTypeError("day count cannot be negative")
    return days


def retire(gh: str, items: list[dict], days: int, dry_run: bool) -> list[dict]:
    """Archive Done items closed longer than `days` ago; return what remains.

    Under `dry_run` nothing is archived, but the return value still excludes
    the retirement candidates, so the caller plans over the board a real run
    would leave behind rather than over today's.
    """
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    closed = closed_at_by_item(gh)

    stale = [i for i in items
             if bucket(i) == 2 and (closed.get(i["id"]) or cutoff) < cutoff]
    undated = [i for i in items if bucket(i) == 2 and i["id"] not in closed]

    if undated:
        print(f"{len(undated)} Done item(s) have no closed date "
              "(Status set by hand?) — left on the board")
    if not stale:
        print(f"nothing Done longer than {days} days — nothing to retire\n")
        return items

    print(f"\nretire {len(stale)} item(s) Done since before "
          f"{cutoff.date().isoformat()}:")
    for item in stale:
        when = closed[item["id"]].date().isoformat()
        print(f"  archive [{when}] {label(item)}")

    stale_ids = {i["id"] for i in stale}
    remaining = [i for i in items if i["id"] not in stale_ids]

    # `remaining` in both branches, deliberately: a dry run that returned the
    # unfiltered list would print a reorder plan over a board the real run has
    # already emptied of these items — positions the run will never produce,
    # in the one printout SKILL.md calls the review.
    if dry_run:
        print()
        return remaining

    print()
    for item in stale:
        try:
            graphql(gh, ARCHIVE, p=PROJECT_ID, i=item["id"])
        except (SystemExit, KeyboardInterrupt):
            # Flush first: stdout is block-buffered when piped, so an unflushed
            # progress log would surface *after* this line and read as if
            # nothing had been archived. Ctrl-C leaves the same partial state
            # as a failed call, and is when a human most wants to be told.
            sys.stdout.flush()
            print("\nboard partially retired — nothing is lost and a re-run "
                  "finishes it; archiving is a fixpoint", file=sys.stderr)
            raise
        print(f"  archived {label(item)}")
    print()
    return remaining


def stays_put(ranks: list[int]) -> set[int]:
    """Indexes into `ranks` forming one longest strictly increasing run.

    `ranks[k]` is the target position of the item now at position k. The
    items of an increasing run are already in target order relative to each
    other, so they need no move; the longest such run leaves the fewest to
    move. Patience sorting, O(n log n).
    """
    tails: list[int] = []            # tails[L] = index ending the best run of length L+1
    back: list[int | None] = []      # back[k] = index before k in its run
    for k, r in enumerate(ranks):
        lo, hi = 0, len(tails)
        while lo < hi:
            mid = (lo + hi) // 2
            if ranks[tails[mid]] < r:
                lo = mid + 1
            else:
                hi = mid
        back.append(tails[lo - 1] if lo else None)
        if lo == len(tails):
            tails.append(k)
        else:
            tails[lo] = k
    keep: set[int] = set()
    k = tails[-1] if tails else None
    while k is not None:
        keep.add(k)
        k = back[k]
    return keep


def plan_moves(current: list[dict], desired: list[dict]) -> list[tuple[dict, dict | None]]:
    """The fewest (item, after) moves that turn `current` into `desired`.

    Moves are listed in target order and each puts an item right after its
    target predecessor (None: the top). That predecessor is either an item
    that stays put or one moved earlier in the list, and no staying item can
    sit between an item's target predecessor and its target successor — the
    ranks between them all belong to moved items — so each move lands where
    the target order wants it.
    """
    rank = {item["id"]: n for n, item in enumerate(desired)}
    keep = {current[k]["id"]
            for k in stays_put([rank[i["id"]] for i in current])}
    return [(item, desired[n - 1] if n else None)
            for n, item in enumerate(desired) if item["id"] not in keep]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan, mutate nothing")
    parser.add_argument("--archive-after-days", type=archive_after,
                        default=DEFAULT_ARCHIVE_AFTER_DAYS, metavar="N|never",
                        help="retire Done items closed more than N days ago; "
                             "'never' keeps them all "
                             f"(default {DEFAULT_ARCHIVE_AFTER_DAYS})")
    parser.add_argument("--gh", default=None,
                        help="path to the gh binary (default: local.toml, then PATH)")
    args = parser.parse_args()
    global GH_SOURCE
    if args.gh is None:
        args.gh, GH_SOURCE = find_gh()
    else:
        GH_SOURCE = "--gh"

    raw = run([args.gh, "project", "item-list", PROJECT_NUMBER,
               "--owner", OWNER, "--format", "json", "--limit", "500"])
    current = json.loads(raw).get("items", [])
    if not current:
        sys.exit("project returned no items — check the `project` token scope")

    names = ["fair game", "deferred", "done"]
    counts = [sum(1 for i in current if bucket(i) == b) for b in (0, 1, 2)]
    print(f"{len(current)} items: "
          + ", ".join(f"{n} {c}" for n, c in zip(names, counts)))

    if args.archive_after_days is None:
        print("--archive-after-days never: keeping every Done item")
    else:
        current = retire(args.gh, current, args.archive_after_days, args.dry_run)

    # Stable partition: sorted() is stable, so equal keys keep their order.
    desired = sorted(current, key=bucket)

    if [i["id"] for i in current] == [i["id"] for i in desired]:
        print("board already in order — nothing to reorder")
        return 0

    moves = plan_moves(current, desired)
    # 1-based target position, to match the board's own numbering.
    where = {item["id"]: n + 1 for n, item in enumerate(desired)}
    print(f"{len(moves)} of {len(current)} items move; the rest are already "
          "in order relative to each other and stay put.\n")
    for item, _ in moves[:20]:
        print(f"  -> {where[item['id']]:>3} [{names[bucket(item)]:<9}] "
              f"{label(item)}")
    if len(moves) > 20:
        print(f"  … and {len(moves) - 20} more")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    print()
    for done, (item, after) in enumerate(moves):
        argv = [args.gh, "api", "graphql", "-f", f"query={MOVE}",
                "-f", f"p={PROJECT_ID}", "-f", f"i={item['id']}"]
        if after is not None:
            argv += ["-f", f"a={after['id']}"]
        try:
            run(argv)
        except (SystemExit, KeyboardInterrupt):
            sys.stdout.flush()
            print(f"\nboard partially reordered — {done} of {len(moves)} "
                  "moved; re-run to finish, the pass is a fixpoint",
                  file=sys.stderr)
            raise
        print(f"  {done + 1}/{len(moves)} {label(item)}")

    print("\nreordered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
