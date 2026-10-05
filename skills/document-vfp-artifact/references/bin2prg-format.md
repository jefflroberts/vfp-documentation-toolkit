# Reading FoxBin2PRG text twins

FoxBin2PRG converts VFP's binary, table-based source files into a deterministic
text representation (so they diff and version cleanly). The extension's last
letter becomes `2`: `.scx→.sc2`, `.vcx→.vc2`, `.frx→.fr2`, `.lbx→.lb2`,
`.mnx→.mn2`, `.dbc→.dc2`, free `.dbf→.db2`, `.pjx→.pj2`. Native `.prg` files
are already text.

**Ground truth beats this summary.** Before documenting a type for the first
time on a new app, open one twin alongside a finished peer doc (PROJECT.md
"Peer docs") and compare — the corpus shows exactly how each construct was
rendered. `python <toolkit>/tools/foxparse.py <twin>` gives a structured view
to cross-check against.

Every twin starts with a header comment naming the source file and code page,
then the content. Twins say "Only for VFP 9 binaries" but convert VFP 6 and 7
era binaries without complaint; the table layouts did not change.

## Forms (`.sc2`) and class libs (`.vc2`)
Rendered as VFP class source: a `DEFINE CLASS <name> AS <parent> [OF <lib>]`
block per class, with:
- `*< CLASSDATA ... />` and `*<PropValue>` sections holding stored
  (non-default) properties, including the control tree. Nested controls are
  flattened into dotted object paths (`pgfMain.Page2.grdItems.Column3.Text1`),
  not nested class blocks.
- `PROCEDURE <event-or-method>` … `ENDPROC` blocks holding code bodies.
- A trailing `ENDDEFINE`.
- Older libraries often put a `&& comment` after the parent class on the
  `DEFINE CLASS` line; it is the class's designer-time description.

A form twin holds two classes: the form and its DataEnvironment. Capture the
**container hierarchy** from the dotted paths. A `.vc2` simply has several
`DEFINE CLASS` blocks; document every one.

## Reports (`.fr2`) and labels (`.lb2`)
A flat list of `<Reportes ...>` records, one per FRX row. Each has an
`objtype` (1 printer setup, 5 label, 6 line, 7 rectangle, 8 field expression,
9 band, 10 designer metadata, 17 picture, 18 report variable, 23 font
resource, 25 data environment, 26 cursor), coordinates in 1/10000 inch
(`vpos`/`hpos`/`height`/`width`), and properties such as `expr`, `supexpr`
(print-when), font, and picture source. Band records carry the band kind in
`objcode`: 0 Title, 1 Page Header, 2 Column Header, 3 Group Header, 4 Detail,
5 Group Footer, 6 Column Footer, 7 Page Footer, 8 Summary. VFP always writes
Page Header, Detail, and Page Footer, so a three-band report is 1/4/7.
Objects are not tagged with their band: `vpos` is a designer coordinate in
which each band's content is followed by a band bar (20 pixels, 2083.333
units; 19 in some older files), so band k starts at the sum of the previous
heights plus k bars. `foxparse.py` does this assignment and returns
`bands[].objects`.

The objtype 25 record is the data environment: its `expr` holds the
properties (`AutoOpenTables`, `InitialSelectedAlias`), its `tag` the method
code (`PROCEDURE Init ... ENDPROC`). Each objtype 26 record is a cursor
(`Alias`, `CursorSource`, `Database`, `Filter`). Reports do declare cursors;
one with none renders against whatever alias the caller left open. The
objtype 1 record holds the saved printer environment twice: readable
`DRIVER=/DEVICE=/OUTPUT=` lines in `expr` and the binary DEVNAMES in `tag`;
the two can disagree. Note it if it names a specific device or server.
Report variables (objtype 18) keep the value expression in `expr`, the
initial value in `tag`, calculation in `totaltype`, and reset in
`resettotal` (1 report, 2 page, 3 column, 6+ group N). A `picture` value on
a field or label is its format mask, not an image; only objtype 17 records
are images, and `offset = 1` there means the source is a General field.

## Database container (`.dc2`) and free tables (`.db2`)
XML-ish: `<DATABASE>` with `<TABLES>`, `<VIEWS>`, `<RELATIONS>`, and a stored
procedure block; each `<TABLE>` has `<FIELDS>` (name, type, width, decimals,
null, default, validation), header triggers (insert/update/delete/table
valid), and index tags. A `.db2` is one free table in the same shape. For real
row values, query the DBF directly or the SQLite mirror if one was built.

## Menus (`.mn2`)
Emitted as generated menu code between marker comments: `*<MenuType>`,
`*<MenuLocation>` (`REPLACE`, `AFTER _MEDIT`, ...), then `*<SetupCode>`,
`*<MenuCode>` (`DEFINE PAD` / `ON PAD .. ACTIVATE POPUP` / `DEFINE POPUP` /
`DEFINE BAR` with prompts, `KEY` shortcuts, `SKIP FOR` conditions, `MESSAGE`
status text, and `ON SELECTION BAR|POPUP|MENU` commands), `*<Procedures>`
(bar procedures named `BAR_n_OF_popup_FB2P`; GENMENU's `.mpr` names them
`_07y0s8..`), and `*<CleanupCode>`. A designer comment on a pad or bar
follows its `MESSAGE` clause as `&& ..`. Two artifacts: every separator bar
(`"\-"`) gets an `ON BAR .. ACTIVATE POPUP` to an empty generated popup, and
the `REPLACE` location's `SET SYSMENU TO` / `SET SYSMENU AUTOMATIC` pair is
not emitted (it is implied by the header). Bars named `_med_*`, `_mst_*`,
`_mwi_*`, `_mpr_*` are VFP system bars with built-in behaviour and no `ON
SELECTION`. `foxparse.py` parses all of this (`parse_mn2`); cross-check its
pad, bar, popup, and procedure counts against a raw grep, and diff the twin
against any `.mpr` beside it.

## Projects (`.pj2`)
The file manifest (`.ADD('path')` per member, typed), the main program, build
metadata (author, company, version), and the home directory. Summarize
collectively in `01-architecture/projects.md`.

## Watch for
- **Filenames that misrepresent contents** (especially `.vc2`) — trust
  `DEFINE CLASS`, not the file name. PROJECT.md lists the known offenders.
- Formula source stored in memo fields and `EXECSCRIPT()`-ed at runtime —
  PROJECT.md says whether this app does that and where it is recovered.
- `&` macro substitution — note what it evaluates to.
- Absolute or machine-specific paths embedded by the compiler (VFP 9 writes
  the include-file table, with full paths, into report data environment
  records). Treat them as build noise, not source.
- A twin that looks truncated: check the FoxBin2PRG sweep log before assuming
  the artifact is small.
