---
name: document-vfp-artifact
description: >-
  Generate or update a reverse-engineering doc for one Visual FoxPro artifact
  from its FoxBin2PRG text twin — forms (.sc2), class libraries (.vc2), reports
  (.fr2), labels (.lb2), menus (.mn2), database containers (.dc2), free tables
  (.db2), projects (.pj2) — or from a native .prg. Reads the app's
  docs/PROJECT.md for paths, peer docs, and app-specific rules. Use when asked
  to document, re-document, audit, or fill gaps in a VFP app's source docs, or
  to keep the docs consistent with the house conventions.
---

# Document a VFP artifact

Turn one FoxBin2PRG text twin of a Visual FoxPro artifact into a markdown doc
that matches the app's existing docs corpus exactly. The workflow is identical
for every artifact type; only the output **template** differs, so this file
holds the shared procedure and dispatches to a per-type template under
`references/`.

This skill is app-agnostic. Everything that varies per app — where the twins
are, where the docs go, which peer docs to mirror, which gotchas recur — comes
from **`docs/PROJECT.md` in the app's casebook repo**, never from this file.

The canonical statement of the documentation rules is the toolkit's
`methodology/conventions.md`. This skill operationalizes it. If the two ever
disagree, `conventions.md` wins — update this skill to match.

## Step 0: read `docs/PROJECT.md`

Before anything else, read `docs/PROJECT.md` in the repo you are working in.
It supplies:

| Section | What it tells you |
|---|---|
| App | Name, origin, VFP version, one-paragraph purpose |
| Toolkit | Path to the `vfp-documentation-toolkit` checkout (for `tools/foxparse.py` etc.) |
| Source layout | Where the twins live, per type, and how to cite a source path |
| Docs layout | Docs root and the folder map (overrides the dispatch table below if different) |
| Peer docs | Which finished docs to mirror per type, or "none yet" |
| Data access convention | What a "direct table access" landmine is measured against |
| App-specific gotchas | Naming traps, misleading filenames, dead artifacts |
| App-specific landmines | Extra patterns to flag with `NOTE:` |

If `docs/PROJECT.md` does not exist, create it from
`references/project-md-template.md`, fill in what the repo itself reveals, mark
the rest `TBD`, and tell the user what you could not determine. Do not guess
paths.

## Inputs and outputs

- **Source twins** are FoxBin2PRG conversions of the binaries:
  `.scx→.sc2`, `.vcx→.vc2`, `.frx→.fr2`, `.lbx→.lb2`, `.mnx→.mn2`,
  `.dbc→.dc2`, free `.dbf→.db2`, `.pjx→.pj2`. Native `.prg` programs are
  already text. Their location comes from PROJECT.md "Source layout".
- **Docs** are written under the docs root from PROJECT.md (default `docs/`),
  one markdown file per artifact, lowercase name.
- If a doc already exists, **update it in place** — preserve hand-authored
  synthesis (e.g. "Used by", cross-links) and only revise what the twin changed.

## Workflow

1. **Identify the artifact and type** from the file extension (dispatch table).
   Confirm the twin exists where PROJECT.md says it should.
2. **Read the twin in full.** For large forms and classes, read it all before
   writing — control trees and method bodies must be captured depth-first, not
   sampled. See `references/bin2prg-format.md` for how to read each format.
   `python <toolkit>/tools/foxparse.py <twin>` gives a structured JSON view
   (controls, methods, cursors, bands, tables) to cross-check your reading.
3. **Open one peer doc** of the same type, as named in PROJECT.md "Peer docs",
   and match its depth, heading order, and tone. If PROJECT.md says "none yet",
   the doc you write becomes the peer for the next one, so follow the template
   exactly.
4. **Apply the per-type template** from `references/` (dispatch table).
5. **Apply the universal rules** below (header, naming, cross-linking,
   verbatim business logic, landmine flags), plus the app-specific gotchas and
   landmines from PROJECT.md.
6. **Write to the correct folder and name** from the dispatch table (or
   PROJECT.md "Docs layout" if it overrides).
7. **Cross-link** the new or updated doc both ways: link the tables, classes,
   and reports it touches, and add it to the peer index `README.md`.
8. **Self-check** against the Definition of Done before reporting completion.

## Dispatch table

Paths are relative to the docs root.

| Twin ext | Artifact type | Template | Output path |
|---|---|---|---|
| `.sc2` | Form | `references/forms.md` | `04-forms/<name>.md` |
| `.vc2` | Class library (1 file → many classes) | `references/classes.md` | `05-classes/<name>.md` |
| `.fr2` | Report | `references/reports-labels.md` | `06-reports/<name>.md` |
| `.lb2` | Label | `references/reports-labels.md` | `06-reports/<name>.md` |
| `.mn2` | Menu | `references/menus.md` | `07-menus/<name>.md` |
| `.dc2` | Database container | `references/tables.md` | `03-data-model/README.md` for the container, plus `03-data-model/tables/<table>.md` per `TABLE` block inside it |
| `.db2` | Free table | `references/tables.md` | `03-data-model/tables/<name>.md` |
| `.prg` | Standalone program | `references/programs.md` | `08-programs/<name>.md` |
| `.h` | Include file | `references/programs.md` (constants section) | `08-programs/<name>.h.md` |
| `.pj2` | Project | (aggregate, not 1:1) | `01-architecture/projects.md` |

Notes:
- `.vc2` is **one library containing many classes** — document every
  `DEFINE CLASS` block in the file (see `references/classes.md`).
- A `.dc2` carries the container (stored procedures, relations, views) **and**
  the full field list of every contained table. The container is summarized in
  the data-model `README.md`; each table gets its own file under `tables/`.
- `.pj2` projects are summarized collectively in `projects.md`, not one doc each.

## Universal rules (apply to every type)

These are conventions §1/§2/§7/§8/§9. The per-type template covers the body.

### Naming
- One doc per artifact, filename = artifact name **lowercased**:
  `frmOrder.sc2` → `frmorder.md`; `CUSTOMER` table → `customer.md`.
- Folder index files are always `README.md`.

### Required header (top of every doc)
```markdown
# <Artifact name>

| Source file | Type | Path |
|---|---|---|
| `ordentry.scx` | Form | `forms/ordentry.sc2` |

**Purpose:** One sentence — what this artifact does in the business.

**Used by:** Bullet list of forms/programs/reports that reference it (fill during
a synthesis pass; OK to leave `TBD` initially).

**Related docs:** `[[link-to-related.md]]` cross-references.
```
The `Path` column is the twin's path written the way PROJECT.md "Source
layout" says to cite it (normally repo-relative).

### Cross-linking
Use `[[file.md]]` or relative MD links. Liberally link forms ↔ tables ↔ classes ↔
reports so a reader can reach every related piece in one click.

### Business logic is QUOTED, not only paraphrased
When you find a formula or rule, copy the **verbatim FoxPro expression** into a
fenced ` ```foxpro ` block, THEN explain it in plain English underneath. A
rebuilder needs the original source to verify intent.

### Flag landmines with a `NOTE:` line
Add a **NOTE:** wherever you see:
- Hard-coded customer/dealer IDs, account numbers, machine names, UNC paths
- `MESSAGEBOX` / hard-coded English strings (i18n candidates)
- `INKEY()`, `WAIT WINDOW`, `DOEVENTS` (timing-sensitive)
- Direct `USE` / `SELECT N` that bypasses the app's data-access convention
  (PROJECT.md says what that convention is, or that there is none)
- Empty/dead branches (`IF .F.`)
- References to files outside the project (`..\..\..\somewhere\...`)
- `&` macro substitution — note what it evaluates to (hard to rebuild)
- Anything listed under "App-specific landmines" in PROJECT.md

## Definition of Done

- [ ] `docs/PROJECT.md` was read first and its gotchas applied.
- [ ] Header table + Purpose + Used-by + Related docs present.
- [ ] Correct per-type template sections, in the corpus's heading order.
- [ ] Every non-trivial formula/event body quoted verbatim, then explained.
- [ ] Landmines flagged with `NOTE:`.
- [ ] Cross-links added both directions; peer `README.md` index updated.
- [ ] Filename lowercased, written to the dispatch-table path.
- [ ] Depth matches a peer doc of the same type (no sampled/partial control trees).
