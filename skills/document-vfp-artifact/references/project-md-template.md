# `docs/PROJECT.md` template

Copy this into the app's casebook repo as `docs/PROJECT.md` and fill it in. The
`document-vfp-artifact` skill reads it before documenting anything; every
app-specific fact lives here, not in the skill.

```markdown
# <App name> — documentation project config

Read by the `document-vfp-artifact` skill before any doc is written.

## App

- **Name:** <app name>
- **Origin:** <vendor / in-house / sample; who wrote it and when>
- **VFP version:** <version the binaries were last written in; version it builds under now>
- **What it does:** <one paragraph>

## Toolkit

- **Path:** `<absolute path to the vfp-documentation-toolkit checkout>`
- **Parser:** `python <toolkit>/tools/foxparse.py <twin>` (add `--summary` for one line per artifact)

## Source layout

Twins are FoxBin2PRG text conversions committed beside their binaries.

| Type | Twin ext | Where |
|---|---|---|
| Forms | `.sc2` | `<glob, e.g. forms/*.sc2>` |
| Class libraries | `.vc2` | `<glob>` |
| Reports | `.fr2` | `<glob>` |
| Labels | `.lb2` | `<glob or "none">` |
| Menus | `.mn2` | `<glob>` |
| Database container | `.dc2` | `<path>` |
| Free tables | `.db2` | `<glob or "none">` |
| Programs | `.prg` | `<glob>` |
| Project | `.pj2` | `<path>` |
| Include files | `.h` | `<glob>` |

**Cite a source path as:** `<repo-relative, e.g. forms/ordentry.sc2>`

## Docs layout

- **Docs root:** `docs/`
- **Folder map:** the skill's default (`01-architecture`, `02-domain`,
  `03-data-model/tables`, `04-forms`, `05-classes`, `06-reports`, `07-menus`,
  `08-programs`, `09-business-logic`) unless listed differently here.

## Peer docs

| Type | Mirror this doc |
|---|---|
| Form | `<docs/04-forms/x.md>` or "none yet" |
| Class library | ... |
| Report | ... |
| Menu | ... |
| Table | ... |
| Program | ... |

## Data access convention

<How the app is supposed to open tables (a data-access class, a framework
method, the DataEnvironment) so that direct `USE` / `SELECT N` can be flagged
as a deviation. Or: "None; every form opens tables directly, so do not flag it.">

## App-specific gotchas

- <misleading filenames, which of several similar artifacts is the live one,
  where business rules actually live, cross-project contamination>

## App-specific landmines

- <extra patterns to flag with NOTE:, e.g. hard-coded server names, a
  particular global object, registry keys>

## Out of scope / dead artifacts

- <files in the repo that should not be documented, and why>
```
