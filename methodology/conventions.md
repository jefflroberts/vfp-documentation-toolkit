# Documentation Conventions (for contributors / agents)

App-agnostic. Everything specific to one app (paths, peer docs, gotchas) lives in that app's
casebook `docs/PROJECT.md`, which the `document-vfp-artifact` skill reads first.

Every documentation page must follow these conventions so the corpus is consistent and a future
reader (human or LLM) can reason across files.

## 1. File naming

* One MD per VFP artifact: `frmCustomer.sc2` → `04-forms/frmcustomer.md`. Lowercase only.
* Table MDs use the VFP table name verbatim, lowercased: `tblOrder.db2` → `03-data-model/tables/tblorder.md`.
* Index files in every folder are `README.md`.

## 2. Required header for every MD

```markdown
# <Artifact name>

| Source file | Type | Path |
|---|---|---|
| `frmCustomer.scx` | Form | `Source/frmCustomer.sc2` |

**Purpose:** One sentence — what this artifact does in the business.

**Used by:** Bullet list of forms/programs that reference it (fill in during synthesis pass; OK to leave TBD initially).

**Related docs:** `[[link-to-related.md]]` cross-references.
```

## 3. Form documentation template

```markdown
## Form metadata
- Base class / parent: ...
- Caption: ...
- Modal: yes/no
- Window state / size / position

## DataEnvironment
| Cursor name | Alias | Source table | Database | Order | Filter |
|---|---|---|---|---|---|

## Controls (depth-first)
For each control:
- **Container path** — `Form.Pageframe1.Page2.Grdgrid1.Column3.Text1`
- **Class:** `textbox` (or `cntfortespnshowfraction` etc.)
- **Caption / Picture / InputMask:** ...
- **ControlSource:** `tblorderdetails.nwidth` (data binding)
- **Events with code:** Click / Valid / Init / RangeHigh / RangeLow ...
  ```foxpro
  <copy of code body>
  ```
- **Plain-English explanation** of what the code does.

## Form methods (custom)
For each non-inherited method: signature, body, explanation.

## Tables read / written
Bullet list. Mark each as read | write | both.

## Inter-form navigation
Buttons that open other forms; events that broadcast to other controls.
```

## 4. Class library template

```markdown
## Classes in this library
For each class:

### className (extends parentClass [from somelib.vcx])
- **Purpose:**
- **Custom properties:** name — type — default — meaning
- **Custom methods:** name(params) — returns — purpose
  - **Body:** code + explanation
- **Overridden inherited methods:** name — what changed and why
```

## 5. Table template

```markdown
## Schema
| # | Field | Type | Width | Dec | Null | Default | Field-valid expr | Comment |
|---|---|---|---|---|---|---|---|---|

## Triggers (from table header)
- Insert: `<expr>`
- Update: `<expr>`
- Delete: `<expr>`
- Table valid: `<expr>` — `<error text>`

## Indexes (.cdx tags)
| Tag | Type | Expression | For | Unique |
|---|---|---|---|---|

## Stored procedure references
(any `sp_*` referenced in triggers — see `appdata.dbc` stored procs)

## Used by
Forms / reports / programs that read or write this table.

## Sample / notable rows
If small lookup table: include all rows or a representative subset.
```

## 6. Report template

```markdown
## DataEnvironment
Tables used, relations.

## Bands & content
For each band (Title, Page Header, Group Header N, Detail, Group Footer N, Page Footer, Summary):
- Height
- Fields & expressions (verbatim) — explain non-trivial ones
- Conditional suppression rules

## Page setup
Orientation, paper size, margins, scale, copies.

## Triggered from
Form / menu items that print this report.
```

## 7. Cross-linking

Use `[[file.md]]` style or relative MD links. Liberally cross-link forms ↔ tables ↔ classes ↔
reports. The goal is that someone reading any single file can find every related piece in one
click.

## 8. Business logic must be quoted, not paraphrased only

When you find a formula or rule (e.g., a price calculation, a credit-limit check), copy the
**verbatim FoxPro expression** into the doc inside a code fence, THEN explain it in plain English
underneath. Future-you needs the original source to verify intent during a rebuild.

## 9. Things to flag

If you see any of these, put a **NOTE:** line in the doc:
* Hard-coded customer IDs, dealer IDs, account numbers, machine names, UNC paths
* `MESSAGEBOX` / hard-coded English strings (i18n candidates)
* `INKEY()`, `WAIT WINDOW`, `DOEVENTS` (timing-sensitive code)
* Direct `USE` / `SELECT N` that bypasses the app's data-access convention (the casebook's `docs/PROJECT.md` says what that convention is, or that there is none)
* Empty/dead branches (e.g., `IF .F.`)
* References to files outside the project (`..\..\..\somewhere\...`), and machine-specific paths, server names, or printer devices
* `&` macro substitution (these become hard to rebuild — note what they evaluate to)
