### `items/NNN-*.md`

- Filename begins with the zero-padded number. First `#` heading is
  `# Item NNN — Title`. *(status report title parse)*
- **No status field** in the header — status lives only in `progress.md`. The
  header carries `Created`, Stage, Queue, Objectives, Suggested branch, and a
  mandatory **Assumptions** block (see the item template). *(spec-author,
  validator)*
- **`## Dependencies` blocks `aide claim`.** Every item number named in this
  section (any of the accepted forms in the table above) is read as something
  this item is blocked on until it is ✅/🚧 — `aide claim` skips a `📋` item
  while any of its dependencies is still open. Text at or after a literal
  `**Downstream` marker is excluded from that scan, so a forward-looking aside
  ("**Downstream:** item 099 depends on this item's CI job") does not register
  as a backward blocker — put such asides after the marker, never before it.
  The rest of any line from a `Blocks:` marker on is excluded too, so quoting
  a human-gate row's reach ("waits on Gate 3 — `Blocks: 119, 120, 121`") does
  not turn the gate's whole reach into dependency edges. *(aide claim)*
