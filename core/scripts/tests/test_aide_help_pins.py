"""The `-h` description blocks, pinned to the code that makes them true.

`aide <verb> -h` is the **authoritative** statement of what a verb does: the
sections stopped restating verb mechanism and point here instead
(`conventions.md` §1, and the copies rule's rung 1 — "the text is mechanism the
code owns"). An authoritative statement with nothing holding it to the code is
the shape that shipped a two-release-stale rollup in a template header, so a
prose statement of behaviour the code owns is pinned by a test that **exercises
the code**, never by a second prose copy to quote against.

`test_progress_help_states_the_rollup_the_code_applies` (issue #192) is the
model and the seventh entry below: it transcribes the help sentence as a
predicate and compares it to `rollup_status` over the whole input space.
`HELP_PINS` is the register for all seven verbs. Each entry is
``(sentence, "module::function")``:

* the **sentence** is a load-bearing clause quoted from the help `argparse`
  renders, compared after a normalisation that absorbs reflow, emphasis and
  case (`_normalise`, a local minimal copy of `tests/_delivered.normalise` —
  this directory ships to consumers, where `tests/` does not exist). A reword
  that drops the clause fails `test_every_pinned_sentence_is_still_in_the_help`,
  which is what makes it a pin and not a comment.
* the **guard** names the test that exercises the claim. A deleted or renamed
  guard fails `test_every_guard_resolves`. Each one was read before it was
  named: a guard that merely sits near the behaviour proves nothing, so where
  no existing test exercised a claim, one was written — in this module where a
  document tree is enough, in the verb's own module where git is.

The pins were audited against the code as they were written, and five help
sentences were corrected in 1.49.4 rather than pinned as they stood. Those are
in `CHANGELOG.md` under *Fixed*; the comment on each pin below names the code
that makes the sentence true.

**Deliberately unpinned**, and why — the rest of the six blocks is here:

* *"a finding against one is an error no later item can clear"* (`check`),
  *"an excluded item is never offered"*, *"whichever builds second inherits the
  first's edits"* — rationale for a rule pinned beside them, not a second rule.
* *"since the row is dropped from every check it would have fed"*, *"the
  goal-level mirror of that over-claim"*, *"a normal state rather than a
  defect"* (twice), *"that would be recommending the deletion of an open PR's
  head branch"*, *"Because in `pr` mode nothing inside the loop observes the
  merge"*, *"so none of them lives only in one commit's diff"*, *"since what it
  blocks is unknown"* — same: the reason a pinned behaviour is what it is.
* *"left for `aide scope` to judge"*, *"`aide progress -h` states the rollup"*,
  *"(like `aide sync`)"*, *"the same merge-tree comparison `gc` uses"* —
  pointers at another verb, rung 1. A pointer names where the rule is; it
  states none of its own.
* *"the wrong cell count (a '|' inside a cell, usually), a Stage cell that is
  not an integer, an objective coverage row not starting G<n>, an empty Target
  cell, a summary or objective Status cell with no icon"* (`check`) — the
  enumeration of `_summary_row_problem` / `_objective_row_problem` /
  `_target_row_problem`, each already pinned row-shape by row-shape in
  `test_aide_table_rows.py`'s `CASES` table. Pinning the list here would be a
  third copy of the same list, not a second guard.
* *"the report names that gate, what it blocks and who may resolve it, rather
  than an unexplained 'none left'"* (`claim`) — the *wording* of a report,
  which `test_aide_gates.py` holds phrase by phrase; the behaviour half ("it
  will not offer a blocked item") is pinned.
* The `-h` **option** help (`--queue`, `--base`, `--yes`, …). Argparse prints
  those below the description; this row is the description blocks, and an
  option line is one clause about one flag rather than a statement of what the
  verb does.

Stdlib + pytest only, and Windows-safe: no subprocess, no POSIX paths, and the
guard modules are located beside this file rather than by an import path.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

_HERE = Path(__file__).resolve().parent
_MODULE_PATH = _HERE.parent / "aide.py"
_spec = importlib.util.spec_from_file_location("aide_cli_help_pins", _MODULE_PATH)
aide = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = aide
_spec.loader.exec_module(aide)  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# reading the help, and comparing a quotation with it
# --------------------------------------------------------------------------- #
_MARKERS = str.maketrans("", "", "*_`")


def _normalise(text: str) -> str:
    """The comparable form of a passage — what it says, not how it is set.

    `tests/_delivered.normalise` is the same four transforms over the same
    reasons, and is deliberately not imported: `core/scripts/tests/` is
    installed into every consumer as `.aide/scripts/tests/`, where `tests/`
    does not exist. The table-row transform of that module is dropped rather
    than copied — no `-h` block contains a markdown table — and what remains is
    reflow, emphasis and case, which is what separates a rewrapped help string
    from a reworded one.
    """
    return " ".join(text.translate(_MARKERS).split()).casefold()


def _help_for(verb: str) -> str:
    """The help text `argparse` renders for *verb* — the authoritative copy.

    Reached through the `_SubParsersAction` the way the model test reaches it,
    so the pins read exactly the string a consumer sees, line wrapping and all,
    rather than the source literals it was assembled from.
    """
    parser = aide.build_parser()
    return next(action.choices[verb].format_help()
                for action in parser._actions
                if isinstance(action, argparse._SubParsersAction))


# --------------------------------------------------------------------------- #
# the register
# --------------------------------------------------------------------------- #
#: verb -> [(sentence quoted from `aide <verb> -h`, "module::function")]
HELP_PINS: Dict[str, List[Tuple[str, str]]] = {

    # ---------------------------------------------------------------- check --
    "check": [
        # `queue_spec_findings`, row 1: severity "warning", kind
        # "may-change-overlap", and `bookkeeping` excluded from it.
        ("two items claiming one path under May change (warning)",
         "test_aide_queue_specs::test_reports_two_items_claiming_the_same_path"),
        # Same function, rows 2+3: severity "error", kind "changes-pinned-state".
        ("one item changing a path another pins under Asserts against (error)",
         "test_aide_queue_specs::test_changing_a_siblings_pinned_path_is_an_error"),
        # `_dependency_cycles(graph)` -> kind "dependency-cycle", severity error.
        ("a dependency cycle",
         "test_aide_queue_specs::test_dependency_cycle_is_an_error"),
        # The typo pass: `not has_spec and not in_a_queue` -> "unknown-dependency".
        ("a dependency on an item that exists nowhere",
         "test_aide_queue_specs::test_unknown_dependency_is_a_warning"),
        # `spent = {n for n in numbers if item_status... in ("complete",
        # "excluded")}`, then `ordered = sorted(n for n in declared if n not in
        # spent)` — the filter runs before the pair loop, so both sides go.
        ("Spent items (✅ merged or ❌ excluded in progress.md) are "
         "discounted on both sides of every comparison",
         "test_aide_queue_specs::"
         "test_a_spent_item_is_discounted_on_both_sides_of_every_comparison"),
        # `if a in built_after.get(b, ())` — a's edit is excused against b's
        # pin, never b's against a's.
        ("A declared dependency is discounted in one direction",
         "test_aide_queue_specs::test_the_dependency_exemption_is_directional"),
        # `_built_after(ordering_edges)` closes the relation transitively.
        ("when the pinning item names the changing one under ## Dependencies, "
         "directly or through a chain of items on the same queue, the edit "
         "landing cannot break its pin",
         "test_aide_queue_specs::test_a_transitive_dependency_exempts_the_pair"),
        # `ordering_edges` keeps only deps whose status is in BLOCKING_STATUSES
        # ("planned", "in-progress", "in-review") — so ✅/❌/⏸️ edges are dropped.
        ("a dependency claim no longer waits for (✅, ❌, ⏸️) "
         "earns no exemption",
         "test_aide_queue_specs::test_a_deferred_dependency_earns_no_exemption"),
        # The filter is on edges, not pairs, so an intermediate settles it too.
        ("neither does a chain whose middle item no longer blocks",
         "test_aide_queue_specs::"
         "test_a_chain_through_a_deferred_link_earns_no_exemption"),
        # `graph = {... if item_status.get(num) in BLOCKING_STATUSES}`.
        ("The cycle check keeps only items whose status still blocks a claim",
         "test_aide_queue_specs::test_a_deferred_item_drops_out_of_the_cycle_graph"),
        # ⏸️ is absent from `spent`, so a deferred item is still in `ordered`.
        ("deferred items stay in the path comparisons",
         "test_aide_queue_specs::test_a_deferred_item_stays_in_the_path_comparison"),

        # `run_checks`: `has_stage_table` / `has_obj_table` / `sections`, each
        # appending to `errors`.
        ("a missing stage summary table, objective coverage table or stage "
         "section",
         "test_aide_help_pins::"
         "test_check_errors_on_each_missing_table_and_on_missing_stage_sections"),
        # `if summ == "complete" and derived and derived != "complete"` — the
        # measure is `rollup_status`, under which a ❌ bullet counts toward ✅.
        ("a stage summary row marked ✅ over a stage whose deliverables do "
         "not roll up to ✅",
         "test_aide_help_pins::test_the_summary_over_claim_is_measured_by_the_rollup"),
        # `if t.kind == "not-met"` under an objective whose status is complete.
        ("an objective marked ✅ over an Outcome target that is ❌ Not met",
         "test_aide_core::test_check_flags_objective_complete_over_unmet_target"),
        # `unreadable_row_errors` over `_PROGRESS_TABLES` — all four of them.
        ("a row of the stage summary, objective coverage, Outcome targets or "
         "Human gates table that its reader cannot use",
         "test_aide_table_rows::"
         "test_a_mis_shaped_row_trades_its_error_for_an_unreadable_row_error"),
        # `_table_rows`: the heading's section, plus — for an `anywhere` table
        # whose section holds no readable row — every block a row is taken from.
        ("Each table is read under its template heading, or, for a summary or "
         "objective table without one, wherever its rows are found",
         "test_aide_table_rows::"
         "test_a_summary_under_another_heading_is_still_checked_row_by_row"),
        # `cmd_check`: `return 1` iff `errors`; warnings are only printed.
        ("a warning never moves the exit code — only an error does",
         "test_aide_help_pins::test_a_warning_alone_still_exits_zero"),
        # `if derived == "complete" and summ and summ != "complete"` — the
        # mirror of the error above, and the same measure.
        ("a stage whose deliverables roll up to ✅ under a summary row "
         "that is not",
         "test_aide_help_pins::"
         "test_a_rolled_up_stage_under_a_lesser_summary_row_is_a_warning"),
        # `if header_status and summ and header_status != summ`.
        ("a stage header disagreeing with its summary row",
         "test_aide_help_pins::"
         "test_a_stage_header_disagreeing_with_its_summary_row_is_a_warning"),
        # `for num in summary_status: if num not in section_nums`.
        ("a summary row with no stage section",
         "test_aide_help_pins::test_a_summary_row_with_no_stage_section_is_a_warning"),
        # `elif t.kind != "met"` — unverified, or unrecognised.
        ("an objective marked ✅ over a target not yet ✅ Met",
         "test_aide_core::test_check_warns_objective_complete_over_unverified_target"),
        # `if t.kind is None` in run_checks, and `gate_warnings`'s vocabulary
        # branch: one sentence, two tables, so one test crosses both.
        ("an Outcome target or human gate whose Status is not one of its "
         "table's marks",
         "test_aide_help_pins::test_an_unrecognised_status_in_either_table_is_a_warning"),
        # `gate_warnings` over `blocking_gates` — every gate that is not ✅.
        ("every human gate still blocking",
         "test_aide_gates::test_awaiting_gate_warns_with_its_reach"),
        # `_PROGRESS_TABLES` is the whole set, and it is not in it.
        ("The Environment-Gated Capability Verification table is read by no check",
         "test_aide_table_rows::test_the_environment_gated_table_is_read_by_no_check"),

        # `item_spec_warnings` -> the dropped-span lint, one warning per span.
        ("an Authorised paths bullet whose second backtick span or "
         "continuation line is silently dropped, named span by span",
         "test_aide_doc_shape::test_the_lint_names_exactly_what_the_parser_drops"),
        # The double-listing lint compares the two sub-lists by exact path.
        ("one path listed under both May change and Asserts against",
         "test_aide_doc_shape::test_double_listing_a_path_is_reported"),
        # …and deliberately does not match a glob against a literal.
        ("a literal pin under a May-change glob is the legitimate carve-out",
         "test_aide_doc_shape::test_a_literal_pin_under_a_may_change_glob_is_silent"),
        # `_always_authorised_paths(ddir_rel)` matched against Asserts against.
        ("an always-authorised path pinned under Asserts against",
         "test_aide_doc_shape::test_pinning_an_always_authorised_path_is_reported"),
        # `_stale_assumption_pins(text, engine)` — `_feature_line` compares
        # major.minor, so a patch release falsifies nothing.
        ("a marked assumption pinning an engine whose feature line predates "
         "the installed one",
         "test_aide_doc_shape::test_an_assumption_pinned_to_an_older_engine_is_reported"),
        # `for stg, cn, cdate, creason in retracted_criteria(lines)` in
        # run_checks, appending to `warnings`.
        ("every retracted acceptance criterion",
         "test_aide_help_pins::test_a_retracted_criterion_reaches_check_as_a_warning"),
        # `insight_warnings` -> `_INSIGHT_FULL_LOOSE_RE` around a strict `_DATE_RE`.
        ("an insights entry whose shape is off — loose either side of the "
         "date, strict about the date",
         "test_aide_insights::test_the_date_stays_strict_where_the_provenance_relaxed"),
        # `insight_warnings` reads insights.md only; archive-*.md is skipped.
        ("never applied to an archived entry",
         "test_aide_insights::test_an_archive_is_frozen_and_not_shape_checked"),
        # The stale-claim-branch warning skips an item whose status is
        # "in-review": its PR is open, and its branch is not litter.
        ("A \U0001f50d item's claim branch is not reported stale",
         "test_aide_git::test_check_does_not_call_a_branch_awaiting_review_stale"),
    ],

    # ------------------------------------------------------------- progress --
    "progress": [
        # The model (issue #192), and the reason this module exists: the
        # sentence is transcribed as a predicate and compared with
        # `rollup_status` over every combination of the six statuses.
        ("a stage is ✅ when every deliverable bullet in it is ✅ or "
         "❌ and at least one is ✅",
         "test_aide_core::test_progress_help_states_the_rollup_the_code_applies"),
    ],

    # ------------------------------------------------------------- insights --
    "insights": [
        # `_cmd_insights_list`: `shown` filters only on --open/--type, and the
        # ordinal is the entry's position in the file.
        ("number the entries by position and print them all, ticked ones included",
         "test_aide_insights::test_list_prints_every_entry_with_its_number"),
        # `not args.open_only or not e.ticked`.
        ("--open narrows to the untriaged",
         "test_aide_insights::test_list_open_hides_the_closed_history"),
        # `tick_insight_text` — the only function in the CLI that rewrites an
        # existing entry's line.
        ("the one in-place edit — tick entry N with --pointer",
         "test_aide_insights::test_tick_flips_the_box_and_records_where_it_landed"),
        # Same function, the `entry.ticked` branch: `_append_trail`-shaped line.
        ("on an entry already ticked, append a dated trail line instead",
         "test_aide_insights::"
         "test_ticking_an_already_ticked_entry_appends_a_dated_trail_line"),
        # `archive_insight_text` + `insight_quarter(date)`; the entry's lines
        # are moved, not re-rendered.
        ("move closed entries older than --before into "
         "insights/archive-YYYY-QN.md, each with its trail, line for line",
         "test_aide_insights::test_archive_moves_lines_byte_for_byte"),
        # The undatable closed entries come back as the second return value.
        ("an entry it cannot date is named and left behind",
         "test_aide_insights::test_archive_names_the_entry_it_had_to_leave_behind"),
        # `insight_warnings` never opens an archive file.
        ("the archive is frozen and no longer shape-checked",
         "test_aide_insights::test_an_archive_is_frozen_and_not_shape_checked"),
        # `parse_insights` numbers by position, so a move renumbers the rest.
        ("what remains is renumbered, so re-run list",
         "test_aide_insights::test_archive_says_the_numbers_have_shifted"),
        # `resolve_insights_text`: shared prefix, then each side's tail.
        ("write the union of a conflicted inbox — the shared history, then "
         "each side's new entries in capture order",
         "test_aide_insights::"
         "test_the_union_appends_each_sides_new_entries_after_the_shared_history"),
        # `_merge_entry_block` keeps a tick and its pointer from either side.
        ("a tick on either side stands and keeps its pointer",
         "test_aide_insights::test_a_pointer_is_never_dropped_when_only_one_tick_carries_one"),
        # `_merge_trail` sorts on `_TRAIL_DATE_RE`.
        ("trail lines merge in date order",
         "test_aide_insights::test_both_sides_trail_lines_are_kept_in_date_order"),
        # Two pointers are kept and the run says which entry to arbitrate.
        ("two ticks with different pointers keep both and say so",
         "test_aide_insights::test_two_ticks_with_two_pointers_keep_both_and_flag_it_for_a_human"),
        # The prefix check refuses before anything is written.
        ("Refuses, writing nothing, anything that is not a pure append",
         "test_aide_insights::test_a_refusal_leaves_the_markers_exactly_where_they_were"),
        # The shared history must be a prefix of both sides, so anything that
        # rewrote it — a reword, a reorder, a deletion — fails the same check.
        ("a claim reworded, reordered or deleted on one side",
         "test_aide_insights::"
         "test_a_reworded_claim_at_the_tail_is_refused_only_against_the_merge_base"),
        # An archived side is exactly a side whose shared history shrank.
        ("or a side that archived",
         "test_aide_insights::test_an_archive_on_one_side_is_refused_by_the_prefix_check_alone"),
        # `ensure_insights_inbox(..., verb="insights")` on the `list` branch.
        ("A missing insights.md is created from .aide/templates/insights.md by list",
         "test_aide_insights::test_list_on_a_missing_inbox_creates_it_and_reports_an_empty_backlog"),
        # `_commit_created_file` returns the reason; the notice carries it.
        ("committed when git can — on a branch, with an identity; "
         "otherwise it is left untracked and the notice says why",
         "test_aide_insights::test_a_commit_git_refuses_leaves_the_inbox_untracked_not_staged"),
    ],

    # ---------------------------------------------------------------- claim --
    "claim": [
        # `_pick_item` walks `queue_item_numbers(queue_text)`, which is
        # document order — the help said "lowest-numbered" until 1.49.4.
        ("Picks the first \U0001f4cb item the queue lists — its own order, "
         "not the item numbers",
         "test_aide_git::test_claim_offers_the_first_planned_item_the_queue_lists"),
        # `if any(item_status.get(d) in BLOCKING_STATUSES for d in deps)` —
        # the complement of BLOCKING_STATUSES is exactly {✅, ❌, ⏸️}.
        ("whose dependencies have all left the way (✅, ❌ or "
         "⏸️)",
         "test_aide_git::test_pick_item_waits_only_for_a_dependency_that_still_blocks"),
        # `gate_blocked_items` -> `if num in gate_blocked: continue`.
        ("that no unresolved human gate reaches",
         "test_aide_gates::test_claim_skips_a_gated_item_and_offers_the_next"),
        # The "none left" report is built from the gates that actually apply.
        ("It will not offer a blocked item",
         "test_aide_gates::test_none_left_names_only_the_gates_that_apply"),
        # `if block_everything or unreadable_gate_rows(plines): return None`,
        # and `cmd_claim` exits 1 naming the row.
        ("A human-gates row it cannot read holds every item",
         "test_aide_gates::test_claim_holds_every_item_behind_an_unreadable_gate_row"),
        # A defect rather than a normal hold, so not the "none left" exit.
        ("the report names the row and exits 1",
         "test_aide_gates::test_claim_holds_every_item_behind_an_unreadable_gate_row"),
        # `ensure_insights_inbox(repo_root, config, verb="claim")` in `cmd_claim`.
        ("A missing insights.md is created from the template on the way through",
         "test_aide_git::test_claim_creates_the_missing_inbox_on_the_way_through"),
    ],

    # ------------------------------------------------------------------- gc --
    "gc": [
        # `cmd_gc`: `item_status.get(num) == "complete"` -> `branch -D` plus
        # `push origin --delete`, the latter skipped in `local` mode.
        ("Deletes claim branches, local and remote, whose item is ✅ in "
         "progress.md",
         "test_aide_git::test_gc_yes_deletes_local_and_remote"),
        # `_merged_prefixed_branches(repo_root, main, prefix)`.
        ("with --merged also branches already merged into the base",
         "test_aide_git::test_gc_merged_deletes_merged_branch"),
        # `_branch_content_landed` is `merge-tree --write-tree` + a tree
        # comparison, so a squash merge reads as landed where ancestry does not.
        ("On the ✅ ground a branch goes only when `git merge-tree "
         "--write-tree` says merging it into the base would change nothing",
         "test_aide_git::test_gc_deletes_a_single_commit_squash_merge"),
        # `landed is False` -> `skips[br]`, naming `main`.
        ("a branch that still carries unlanded content is skipped with the "
         "base named",
         "test_aide_git::test_gc_refuses_a_tick_whose_branch_has_unlanded_content"),
        # `if args.abandon: targets[br] = reason + "; --abandon"` — checked
        # before the oracle runs at all.
        ("unless --abandon",
         "test_aide_git::test_gc_abandon_deletes_an_unlanded_tick_on_purpose"),
        # `_has_merge_tree` -> `_MERGE_TREE_MIN_GIT = (2, 38)`; `not
        # can_measure` skips rather than falling back to `branch --merged`.
        ("merge-tree --write-tree needs git >= 2.38: on older git the ✅ "
         "ground refuses rather than falling back to a weaker test",
         "test_aide_git::test_gc_refuses_the_tick_ground_on_git_too_old"),
        # The `protected` sweep moves branches out of `targets` before the
        # first `print`, so the preview cannot overstate.
        ("Every skip — checked out, unlanded, git too old — is "
         "decided before anything is printed",
         "test_aide_git::test_gc_preview_does_not_promise_to_delete_the_checked_out_branch"),
        # `print(f"skipping {br} ({_where(br)}): {skips[br]}")`, above the
        # `--yes` branch, so both paths print it.
        ("shown as `skipping <branch> (local/remote): <reason>` on both paths",
         "test_aide_git::test_a_gc_skip_names_the_branch_where_it_lives_and_why"),
        # One `targets` dict, printed as "would delete" or "deleted".
        ("the dry run is exactly the set --yes deletes",
         "test_aide_git::test_gc_preview_and_yes_report_the_same_set"),
    ],

    # --------------------------------------------------------------- status --
    "status": [
        # `elif st == "in-review"` — the note says "awaiting review" and the
        # `run 'aide gc'` string belongs to the `complete` branch only.
        ("A \U0001f50d item's claim branch is reported as awaiting review, "
         "never as stale and never with a `gc` recommendation",
         "test_aide_git::test_status_does_not_recommend_gc_for_a_branch_awaiting_review"),
        # `_landed_review_items(...)`, printed with the `aide sync: ` prefix
        # stripped — the same `_branch_content_landed` oracle `gc` uses.
        ("names any \U0001f50d item whose work has since landed in the base",
         "test_aide_git::test_status_names_a_review_item_whose_work_has_landed"),
        # The four loops over `human_gates`, `_unreadable_rows`,
        # `outcome_targets` and `retracted_criteria` in `cmd_status`.
        ("Every human gate still blocking, every Outcome target not yet ✅ "
         "Met, every retracted acceptance criterion and every progress.md "
         "table row no reader can use is printed too",
         "test_aide_help_pins::test_status_prints_the_four_states_it_promises"),
    ],

    # ---------------------------------------------------------------- scope --
    "scope": [
        # `git merge-base base HEAD` then `git diff --name-only <mb>`, fed to
        # `scope_findings` against the spec's May-change list.
        ("Diffs the branch against the merge-base with the item's base and "
         "reports every changed path outside the spec's ## Authorised paths",
         "test_aide_scope::test_scope_uses_merge_base_not_the_branch_tip"),
        # `scope_findings` returns `(unauthorised, contradictions)`, printed
        # under two different messages.
        ("a path listed under Asserts against and then changed is reported "
         "separately",
         "test_aide_scope::test_findings_separate_unauthorised_from_contradiction"),
        # `_branch_item_number(branch, prefix)` when `args.number is None`.
        ("With no number the item is read from the current claim branch",
         "test_aide_scope::test_scope_explicit_number_overrides_the_branch"),
        # `_is_queue_branch(branch, prefix)` -> message and `return 0`.
        ("a queue branch resolves to no item and is skipped",
         "test_aide_scope::test_scope_skips_a_queue_branch"),
        # `_scope_base_ref` -> `resolve_base`: explicit > recorded > main_branch.
        ("The base is --base if given, else the branch's recorded base, else "
         "main_branch",
         "test_aide_base::test_scope_diffs_against_the_recorded_base"),
        # `_remote_or_local`, applied to the derived answer only.
        ("the two derived answers prefer origin/<base> over the local ref",
         "test_aide_base::test_a_derived_base_prefers_its_origin_counterpart"),
        # `return 0` after "OK", and the queue-branch branch above.
        ("Exit 0: in scope, or nothing to check (a queue branch)",
         "test_aide_scope::test_scope_ok_when_every_change_is_authorised"),
        # `if total: ... return 1`.
        ("1: something changed outside it",
         "test_aide_scope::test_scope_flags_a_file_outside_the_list"),
        # The three `return 2` paths: no spec, `declares_nothing`, no merge-base.
        ("2: could not check (no spec, no section, or no base to diff against)",
         "test_aide_scope::test_scope_reports_a_missing_section_rather_than_passing"),
    ],
}

_PINS = [(verb, sentence, guard)
         for verb, pins in HELP_PINS.items() for sentence, guard in pins]
_IDS = [f"{verb}:{sentence[:48]}" for verb, sentence, _ in _PINS]


# --------------------------------------------------------------------------- #
# the two obligations of a pin
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("verb,sentence,guard", _PINS, ids=_IDS)
def test_every_pinned_sentence_is_still_in_the_help(verb, sentence, guard):
    """Half one: the quotation is still what `argparse` renders.

    Without this the register is a comment — a help block could be reworded out
    from under a guard that keeps passing, which is exactly how a copy goes
    stale while its test stays green. Reflow the sentence freely; change what
    it says and fix the guard, the pin and the code together.
    """
    assert _normalise(sentence) in _normalise(_help_for(verb)), (
        f"`aide {verb} -h` no longer states: {sentence}\n"
        f"Either restore the clause, or reword the pin and re-read {guard} "
        f"to confirm it still exercises what the new wording claims.")


@pytest.mark.parametrize("verb,sentence,guard", _PINS, ids=_IDS)
def test_every_guard_resolves(verb, sentence, guard):
    """Half two: the named test still exists.

    A pin whose guard was deleted or renamed proves nothing, and nothing else
    in the suite would notice — the guard is named in a string. Resolution is
    by import rather than by a text search, so a function moved out of the
    module it is named in fails here too.
    """
    module_name, _, func_name = guard.partition("::")
    assert func_name, f"guard '{guard}' is not 'module::function'"
    module = _guard_module(module_name)
    assert hasattr(module, func_name), (
        f"`aide {verb} -h`'s pin — {sentence} — names "
        f"{guard}, which no longer exists. Point it at the test that exercises "
        f"the claim today, or write one; do not delete the pin.")


_GUARD_CACHE: Dict[str, object] = {}


def _guard_module(name: str):
    """Import a sibling test module under a private name, once.

    A private name, because pytest has already imported these under their own:
    loading them again as `test_aide_git` would replace the collected module
    object mid-run. The file is located beside this one rather than through
    `sys.path`, so the lookup works the same in this repository and in the
    `.aide/scripts/tests/` copy an install ships.
    """
    if name not in _GUARD_CACHE:
        path = _HERE / f"{name}.py"
        assert path.is_file(), f"no guard module {name} beside {_HERE.name}/"
        spec = importlib.util.spec_from_file_location(f"_help_pin_{name}", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        _GUARD_CACHE[name] = module
    return _GUARD_CACHE[name]


def test_the_normaliser_still_sees_a_reword():
    """The register is only a pin while `_normalise` can fail.

    `tests/test_rule_pins.py` holds the same line for the adapter's copies: a
    normaliser loose enough to let a reworded sentence through turns every
    assertion above into one that cannot fail. Reflow, emphasis and case are
    absorbed; a changed word is not.
    """
    assert _normalise("a **stage**\nis  ✅") == _normalise("A stage is ✅")
    assert _normalise("`aide gc`") == _normalise("aide gc")
    assert _normalise("a stage is ✅") != _normalise("a stage is 🚧")
    assert _normalise("all ✅") != _normalise("not all ✅")


def test_every_verb_with_a_description_block_is_registered():
    """Seven blocks, seven entries — the register is the whole row, not a
    sample of it. A verb that grows a description block and no pin would be a
    copy of engine text with nobody deciding anything about it, which is the
    state issue #205 exists to end."""
    described = {verb for verb in _verbs() if _described(verb)}
    assert described == set(HELP_PINS), (
        f"described but unpinned: {sorted(described - set(HELP_PINS))}; "
        f"pinned but no longer described: {sorted(set(HELP_PINS) - described)}")


def _verbs() -> List[str]:
    parser = aide.build_parser()
    return [v for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
            for v in action.choices]


def _described(verb: str) -> bool:
    """Whether *verb* carries a description block, not just option help."""
    parser = aide.build_parser()
    sub = next(action.choices[verb] for action in parser._actions
               if isinstance(action, argparse._SubParsersAction))
    return bool((sub.description or "").strip())


# --------------------------------------------------------------------------- #
# the guards written for this row — document-tree checks, no git needed
# --------------------------------------------------------------------------- #
AIDE_TOML = """\
[project]
name = "Demo"
docs_dir = "docs/aide"
"""

PROGRESS = """\
# Demo — Progress

## Stage summary

| Stage | Title | Objectives | Status |
|-------|-------|-----------|--------|
| 1 | Rules | G1 | 🚧 |

## Objective coverage

| Objective | Delivered by | Status |
|-----------|--------------|--------|
| G1 Rules | Stage 1 | 🚧 |

## Stage 1 — Rules — 🚧

**Deliverables.**
- 📋 Bounds. *(Item 027)*
- 📋 Coverage. *(Item 028)*

**Acceptance.**
- [ ] Rules fire.
"""


def _repo(tmp_path: Path, progress: str = PROGRESS, name: str = "repo") -> Path:
    repo = tmp_path / name
    ddir = repo / "docs" / "aide"
    ddir.mkdir(parents=True)
    (repo / "aide.toml").write_text(AIDE_TOML, encoding="utf-8")
    (ddir / "progress.md").write_text(progress, encoding="utf-8")
    # A loop repo has an inbox, so nothing below is reporting on a file the
    # run itself created.
    (ddir / "insights.md").write_text("# Insight Inbox\n", encoding="utf-8")
    return repo


def _checks(repo: Path):
    return aide.run_checks(repo, aide.load_config(repo), branches=[])


def test_check_errors_on_each_missing_table_and_on_missing_stage_sections(
        tmp_path: Path):
    """The help names three missing things; the existing test named one.

    Each is a separate `errors.append` in `run_checks`, and a document with no
    tables and no stage sections must produce all three — a check that reports
    only the first would leave a reader hunting a second document problem the
    run never mentioned.
    """
    errors, _ = _checks(_repo(tmp_path, progress="# Demo\n\nNo tables, no stages.\n"))
    assert any("missing Stage summary table" in e for e in errors), errors
    assert any("missing Objective coverage table" in e for e in errors), errors
    assert any("no '## Stage N' sections" in e for e in errors), errors


def test_the_summary_over_claim_is_measured_by_the_rollup(tmp_path: Path):
    """The error fires on the rollup, not on "every bullet is ✅".

    Until 1.49.4 the help said "deliverables not all ✅", which predicts an
    error over a stage of ✅ and ❌ — where `rollup_status` says ✅ and the
    check is silent. That is the same falsehood #205 found in the
    `progress.md` template header, one copy over.
    """
    done = PROGRESS.replace("| 1 | Rules | G1 | 🚧 |", "| 1 | Rules | G1 | ✅ |")
    done = done.replace("## Stage 1 — Rules — 🚧", "## Stage 1 — Rules — ✅")

    over_claim = done.replace("- 📋 Coverage. *(Item 028)*",
                              "- 🚧 Coverage. *(Item 028)*")
    over_claim = over_claim.replace("- 📋 Bounds. *(Item 027)*",
                                    "- ✅ Bounds. *(Item 027)*")
    errors, _ = _checks(_repo(tmp_path, progress=over_claim, name="over"))
    assert any("summary marked ✅ but has non-complete deliverables" in e
               for e in errors), errors

    excluded = done.replace("- 📋 Bounds. *(Item 027)*", "- ✅ Bounds. *(Item 027)*")
    excluded = excluded.replace("- 📋 Coverage. *(Item 028)*",
                                "- ❌ Coverage. *(Item 028)*")
    errors, _ = _checks(_repo(tmp_path, progress=excluded, name="excluded"))
    assert not any("non-complete deliverables" in e for e in errors), errors


def test_a_rolled_up_stage_under_a_lesser_summary_row_is_a_warning(tmp_path: Path):
    """The mirror of the error above, and the same measure.

    ❌ counts toward the rollup here too: a stage of ✅ and ❌ under a 🚧
    summary row is the warning, and the pre-1.49.4 wording ("deliverables are
    all ✅") predicted silence.
    """
    text = PROGRESS.replace("- 📋 Bounds. *(Item 027)*", "- ✅ Bounds. *(Item 027)*")
    text = text.replace("- 📋 Coverage. *(Item 028)*", "- ❌ Coverage. *(Item 028)*")
    _, warnings = _checks(_repo(tmp_path, progress=text))
    assert any("all deliverables ✅ but summary shows" in w for w in warnings), warnings


def test_a_stage_header_disagreeing_with_its_summary_row_is_a_warning(
        tmp_path: Path):
    """Two records of one status, and nothing else compares them."""
    text = PROGRESS.replace("## Stage 1 — Rules — 🚧", "## Stage 1 — Rules — 📋")
    _, warnings = _checks(_repo(tmp_path, progress=text))
    assert any("header planned disagrees with summary in-progress" in w
               for w in warnings), warnings


def test_a_summary_row_with_no_stage_section_is_a_warning(tmp_path: Path):
    """A row promising a stage the document does not carry: the deliverables
    behind its status cannot be read, so nothing checks the status at all."""
    text = PROGRESS.replace(
        "| 1 | Rules | G1 | 🚧 |",
        "| 1 | Rules | G1 | 🚧 |\n| 2 | Reporting | G2 | 📋 |")
    _, warnings = _checks(_repo(tmp_path, progress=text))
    assert any("stage 2" in w and "has no '## Stage 2' section" in w
               for w in warnings), warnings


def test_an_unrecognised_status_in_either_table_is_a_warning(tmp_path: Path):
    """One sentence, two tables — so one guard has to cross both.

    A mark neither table recognises is a typo, and in the gates table it also
    keeps blocking: `blocking_gates` is "not ✅ Approved", so an unreadable
    decision is never read as an approval.
    """
    text = PROGRESS + """
## Outcome targets

| Target | Objective | Baseline | Current | Status |
|--------|-----------|----------|---------|--------|
| p95 under 200ms | G1 | 400ms | 250ms | 🤷 Dunno |

## Human gates

| Gate | Blocks | Status | Notes |
|------|--------|--------|-------|
| Sign off the schema | all | 🤷 Maybe | — |
"""
    _, warnings = _checks(_repo(tmp_path, progress=text))
    assert any("unrecognised Status" in w and "p95" in w for w in warnings), warnings
    assert any("Sign off the schema" in w for w in warnings), warnings


def test_a_retracted_criterion_reaches_check_as_a_warning(tmp_path: Path):
    """Retracting is append-only, so without this the withdrawal would live
    only in one commit's diff — which is the quiet the trail exists to prevent.
    A warning, not an error: a withdrawn attestation is a normal state."""
    text = PROGRESS.replace(
        "- [ ] Rules fire.",
        "- [ ] Rules fire. *(verified 2026-07-01)*\n"
        "  - **2026-07-02** → retracted: the host was misread")
    errors, warnings = _checks(_repo(tmp_path, progress=text))
    assert any("was retracted on 2026-07-02" in w for w in warnings), warnings
    assert not any("retracted" in e for e in errors), errors


def test_a_warning_alone_still_exits_zero(tmp_path: Path, capsys):
    """`cmd_check` returns 1 iff `errors` — the whole meaning of the split.

    A run with warnings and no errors exits 0 and prints them, so a consumer
    with a known-normal state (a blocking gate, a retracted criterion) is not
    stopped by it, and an unattended loop does not stall on a report.
    """
    text = PROGRESS + """
## Human gates

| Gate | Blocks | Status | Notes |
|------|--------|--------|-------|
| Sign off the schema | all | ⏳ Awaiting | — |
"""
    repo = _repo(tmp_path, progress=text)
    assert aide.main(["--repo", str(repo), "check"]) == 0
    out = capsys.readouterr().out
    assert "warning:" in out
    assert "aide check: OK" in out


def test_status_prints_the_four_states_it_promises(tmp_path: Path, capsys):
    """`aide status -h` names four, and each has its own loop in `cmd_status`.

    They are one sentence because they share one reason: each is a state
    `progress.md` records and no other line of the report would surface, so a
    reader who never re-opens the document would never learn of it.
    """
    text = PROGRESS + """
## Outcome targets

| Target | Objective | Baseline | Current | Status |
|--------|-----------|----------|---------|--------|
| p95 under 200ms | G1 | 400ms | 250ms | ❌ Not met |

## Human gates

| Gate | Blocks | Status | Notes |
|------|--------|--------|-------|
| Sign off the schema | all | ⏳ Awaiting | — |
| Confirm the budget | 027 | ⏳ Awaiting | a | stray pipe |
"""
    text = text.replace(
        "- [ ] Rules fire.",
        "- [ ] Rules fire. *(verified 2026-07-01)*\n"
        "  - **2026-07-02** → retracted: the host was misread")
    repo = _repo(tmp_path, progress=text)
    assert aide.main(["--repo", str(repo), "status", "--no-fetch"]) == 0
    out = capsys.readouterr().out
    assert "gate 1: Sign off the schema" in out
    assert "target: p95 under 200ms" in out
    assert "retracted: stage 1 criterion 1" in out
    assert "unreadable: progress.md:" in out and "human-gate row" in out
