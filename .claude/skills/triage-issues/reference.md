# Tracker reference

Stable ids and the queries that re-derive them. Ids on GitHub Projects do not
rotate, so these are safe to paste — but if any mutation is rejected with an
unknown-id error, re-run the derivation rather than guessing.

`GH=/mnt/data/ddrobny/.local/bin/gh` throughout (`gh` is not on `PATH`).

## Ids

| Thing | Id |
|---|---|
| Project (`dadrobny/projects/1`, "aide-loop") | `PVT_kwHOByffxc4Bg9iM` |
| `Status` field (single-select) | `PVTSSF_lAHOByffxc4Bg9iMzhf7FgA` |
| `Theme` field (single-select) | `PVTSSF_lAHOByffxc4Bg9iMzhf7FlI` |

`Status` options: `Todo` `f75ad846` · `In Progress` `47fc9ee4` · `Done` `98236657`

`Theme` options:

| Theme | Option id | What it holds |
|---|---|---|
| Reaching the reader | `2cdefa2e` | whether the contract arrives at the role that needs it |
| What the checks decide | `eabc9686` | `aide check` / `aide scope` judging wrongly, or not judging at all |
| Testing the framework itself | `d6eb1372` | **this repo's own suite** — fixture consumer, structural budget, rule pins |
| Correctness | `65b8c907` | the engine does the wrong thing at runtime: crashes, parsing, the installer |
| Naming | `d1401531` | |
| Unattended runs | `9f48758c` | |
| The insight inbox | `2da4ce9d` | |
| Beyond the reference adapter | `162e28eb` | |

The first four are the ones that get confused. **`Testing the framework itself`
means this repo's suite and nothing else** — a lint that polices a *consumer's*
test hygiene is `What the checks decide`, which is why #46 moved there.
`Correctness` is what remains once the checker cluster leaves it, not a
catch-all: an issue that fits nowhere is a sign the option list is short one
entry, not a reason to park it here.

One watch item: `Reaching the reader` is about whether the contract *arrives*.
An issue about what the contract *says* (#121) currently has no better home. One
issue is not a theme; if a second lands, that is the split to make.

Re-derive all of the above:

```bash
$GH api graphql -f query='
query { user(login:"dadrobny"){ projectV2(number:1){ id
  field(name:"Theme"){ ... on ProjectV2SingleSelectField { id name options{ id name } } } } } }'
```

## Views

| # | Name | Layout | Filter | Honours manual order |
|---|---|---|---|---|
| 4 | Board | board | — | yes |
| 5 | Table | table | — | yes |
| 6 | Open | table | `-status:Done AND -label:deferred` | yes |

A view with an explicit sort ignores item position entirely. Check before
concluding a reorder did nothing:

```bash
$GH api graphql -f query='
query { user(login:"dadrobny"){ projectV2(number:1){ views(first:10){ nodes{
  number name filter
  sortByFields(first:5){ nodes{ direction field{ __typename
    ... on ProjectV2Field{name} ... on ProjectV2SingleSelectField{name} } } } } } } } }'
```

## Labels

`bug` · `documentation` · `duplicate` · `enhancement` · `good first issue` ·
`help wanted` · `invalid` · `question` · `wontfix` · **`deferred`** ("Known and
accepted; deliberately not scheduled")

`deferred` is the only scheduling signal. There is no priority label and there
must not be one.

## Mutations

Set a single-select field:

```bash
$GH project item-edit --project-id PVT_kwHOByffxc4Bg9iM --id <PVTI_…> \
    --field-id <PVTSSF_…> --single-select-option-id <option-id>
```

Move an item (this is what `reorder_project.py` drives; `afterId` omitted moves
the item to the top):

```bash
$GH api graphql -f query='
mutation($p:ID!,$i:ID!,$a:ID){ updateProjectV2ItemPosition(
  input:{projectId:$p, itemId:$i, afterId:$a}){ clientMutationId } }' \
  -f p=PVT_kwHOByffxc4Bg9iM -f i=<PVTI_…> -f a=<PVTI_…>
```

Archive an item off the board (reversible with `unarchiveProjectV2Item`;
`reorder_project.py` drives this in its default pass):

```bash
$GH api graphql -f query='
mutation($p:ID!,$i:ID!){ archiveProjectV2Item(input:{projectId:$p, itemId:$i}){
  clientMutationId } }' -f p=PVT_kwHOByffxc4Bg9iM -f i=<PVTI_…>
```

Edit the `Theme` options. **`updateProjectV2Field` replaces the whole option
list**: an option sent with its existing `id` is renamed and every item keeps
it, an option sent without an `id` is created, and an option left out is
**deleted — clearing the field on every item that used it**. Always send the
full list.

`gh api graphql -F` sends only scalars — `-F o=@options.json` passes the file as
a *string* and the mutation rejects it. Post the whole body instead, as
`{"query": …, "variables": {"f": …, "o": [ … ]}}`:

```bash
$GH api /graphql --method POST --input body.json
```

Add an issue:

```bash
$GH project item-add 1 --owner dadrobny --url https://github.com/dadrobny/aide-loop/issues/<N>
```

## Consumer installs

Local checkouts under `/mnt/data/spine/codes`, each carrying the engine version
it was installed at in `.aide/VERSION`:

| Consumer | Path | Notes |
|---|---|---|
| spine-failure-lab | `/mnt/data/spine/codes/spine-failure-lab` | has an `InstructionsLoaded` log |
| SegFACET | `/mnt/data/spine/codes/SegFACET` | |

Read the version an issue was observed under when its body does not say:

```bash
cat /mnt/data/spine/codes/SegFACET/.aide/VERSION
python install.py --into /mnt/data/spine/codes/SegFACET --check   # writes nothing
```

## Issue template

[`.github/ISSUE_TEMPLATE/consumer-report.md`](../../../.github/ISSUE_TEMPLATE/consumer-report.md)
— a Markdown template deliberately, not a YAML issue form: `gh issue create
--template "Consumer report"` can start from Markdown, and cannot from a form.

It reaches the web composer and that `gh` flag only. `gh issue create --body …`
bypasses every template, so an agent filing non-interactively will not carry the
version header unless it is told to.
