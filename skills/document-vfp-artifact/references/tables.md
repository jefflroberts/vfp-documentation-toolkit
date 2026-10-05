# Table / DBC template (`.dc2` / `.db2` → `03-data-model/tables/<name>.md`)

Worked example to mirror: the table peer named in PROJECT.md "Peer docs". If
there is none yet, this template is the standard.

A `.dc2` (database container) twin carries the container itself — stored
procedures, persistent relations, local and remote views — **and** every
contained table's field list, header triggers, and index tags. A `.db2` is one
free table in the same shape.

Document the **container** in `03-data-model/README.md` (table membership,
relations, views, the stored procedure list with one line each). Document each
**table** in its own file under `tables/`, using this template.

After the universal header (see SKILL.md):

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
Any stored procedure called from a trigger, default, or validation rule —
link to the container README where the procedure is listed, and quote the
procedure body if the rule matters to the business.

## Relations
Parent and child relations this table participates in, with the RI rules
(cascade / restrict / ignore) the container declares.

## Used by
Forms / reports / programs that read or write this table.

## Sample / notable rows
If small lookup table: include all rows or a representative subset.
```

Tips:
- If a table has no triggers, no rules, and no relations, say so explicitly —
  absence is a finding the rebuild depends on.
- For lookup/config tables, pull representative rows from the DBF (the
  toolkit's `tools/dbf.py` reads it) or from the SQLite mirror if one exists.
- Memo (`M`) fields that hold executable source or configuration: note it and
  link wherever the content is recovered.
- Record counts and key ranges come from `tools/dbf_header.py` (header only,
  fast) or `tools/dbfscan.py` (reads rows).
