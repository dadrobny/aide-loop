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

Idempotent, and a fixpoint: a second run over an ordered board with nothing
newly stale issues no mutations, and an interrupted run is finished by
re-running it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys

PROJECT_ID = "PVT_kwHOByffxc4Bg9iM"
PROJECT_NUMBER = "1"
OWNER = "dadrobny"
FALLBACK_GH = "/mnt/data/ddrobny/.local/bin/gh"

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


def find_gh() -> str:
    return shutil.which("gh") or FALLBACK_GH


def run(argv: list[str]) -> str:
    # encoding= rather than text=, so a non-UTF-8 default locale cannot mangle
    # an issue title (conventions.md §6, and issue #126).
    proc = subprocess.run(
        argv, capture_output=True, encoding="utf-8", errors="replace"
    )
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
    content = item.get("content") or {}
    number = content.get("number")
    head = f"#{number}" if number else "(draft)"
    return f"{head} {(item.get('title') or '')[:58]}"


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan, mutate nothing")
    parser.add_argument("--archive-after-days", type=archive_after,
                        default=DEFAULT_ARCHIVE_AFTER_DAYS, metavar="N|never",
                        help="retire Done items closed more than N days ago; "
                             "'never' keeps them all "
                             f"(default {DEFAULT_ARCHIVE_AFTER_DAYS})")
    parser.add_argument("--gh", default=find_gh(), help="path to the gh binary")
    args = parser.parse_args()

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

    moved = [(n, i) for n, (i, j) in enumerate(zip(desired, current))
             if i["id"] != j["id"]]
    print(f"{len(moved)} of {len(current)} positions change; "
          "the pass rewrites every position to be deterministic.\n")
    for pos, item in moved[:20]:
        print(f"  -> {pos:>3} [{names[bucket(item)]:<9}] {label(item)}")
    if len(moved) > 20:
        print(f"  … and {len(moved) - 20} more")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 0

    print()
    after: str | None = None
    for pos, item in enumerate(desired):
        argv = [args.gh, "api", "graphql", "-f", f"query={MOVE}",
                "-f", f"p={PROJECT_ID}", "-f", f"i={item['id']}"]
        if after is not None:
            argv += ["-f", f"a={after}"]
        try:
            run(argv)
        except (SystemExit, KeyboardInterrupt):
            sys.stdout.flush()
            print(f"\nboard partially reordered — {pos} of {len(desired)} "
                  "placed; re-run to finish, the pass is a fixpoint",
                  file=sys.stderr)
            raise
        after = item["id"]
        print(f"  {pos + 1}/{len(desired)} {label(item)}")

    print("\nreordered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
