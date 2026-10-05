# Report / label template (`.fr2` / `.lb2` → `06-reports/<name>.md`)

Worked example to mirror: the report peer named in PROJECT.md "Peer docs".
If there is none yet, this template is the standard.

A report `.fr2` twin is a sequence of `<Reportes>` records: band records
(Title, Page Header, Group Header N, Detail, Group Footer N, Page Footer,
Summary) plus field, label, line, box, and picture objects with absolute
coordinates in 1/10000 inch and `supexpr` (print-when) and `expr` properties.
Labels (`.lb2`) are the same structure tuned to label stock.
`python <toolkit>/tools/foxparse.py report.fr2` lists bands, fields, labels,
variables, images, and group expressions; `tools/extract_frx.py` dumps the
raw coordinates from the `.frx` itself.

After the universal header (see SKILL.md):

```markdown
## DataEnvironment
Tables used, relations. If the data environment is empty, say so and name the
form or program that opens the aliases before `REPORT FORM`. If the data
environment has code (an `Init` that runs a form or a query), quote it.

## Bands & content
For each band (Title, Page Header, Group Header N, Detail, Group Footer N,
Page Footer, Summary):
- Height
- Fields & expressions (verbatim) — explain non-trivial ones
- Conditional suppression rules (`supexpr` / print-when)

## Report variables
Name, initial value, value-to-store expression, reset condition.

## Page setup
Orientation, paper size, margins, scale, copies, and the saved printer
device if one is embedded.

## Triggered from
Form / menu items that print this report.
```

Tips:
- Quote field expressions verbatim — a rebuild reproduces these layouts
  coordinate-for-coordinate.
- Note any image/`picture` objects and the file they reference; check the
  file exists in the repo.
- A saved printer environment naming a specific device or server is a
  landmine: the report will try to use it. Flag with `NOTE:`.
- PROJECT.md may name layout-critical reports (the ones the business
  depends on); flag those prominently.
