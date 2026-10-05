# VFP documentation toolkit

Tools and a written method for **documenting, understanding, and porting a Visual FoxPro /
FoxPro application** that nobody fully remembers anymore. Point it at a legacy VFP app and it
helps you:

- turn the binary source (`.scx`, `.vcx`, `.frx`, `.mnx`, `.dbc`, `.pjx`) into structured data
  and a written doc for every form, class, report, menu, program, and table;
- mirror the DBF data into SQLite so you can query it with plain SQL;
- recover the business rules and **prove** you have them right, by reproducing the app's
  stored outputs and printed reports from inputs alone;
- capture every form and report as a regression baseline that a rebuild can be diffed against;
- decide whether and how to port the app to a modern stack.

It was built on real client engagements (a VFP 9 manufacturing app and a VFP 6 distribution
ERP) and tested on Microsoft's Tastrade sample app.

## Requirements

- **Python 3.6 or newer** for the tools in `tools/` (standard library only; developed on 3.14).
  The data converter also runs on Python 3.4 so it works on Windows XP and 7 machines.
- **[FoxBin2PRG](https://github.com/fdbozzo/foxbin2prg)**, run from the VFP IDE, to turn the
  binaries into text. It is not bundled.
- **Windows PowerShell and VFP 9** for the baseline-capture helpers.
- **[Claude Code](https://claude.com/claude-code)** only if you want the `document-vfp-artifact`
  skill to write the per-artifact docs for you. Every Python tool works without it.

## Quick start

```sh
git clone https://github.com/jefflroberts/vfp-documentation-toolkit.git

# 1. Find hard-coded credentials before you commit the app's source anywhere
python vfp-documentation-toolkit/tools/security/scan_secrets.py path/to/app/source

# 2. After running FoxBin2PRG over the app, summarize what it produced
python vfp-documentation-toolkit/tools/foxparse.py path/to/app/source --summary

# 3. Census the data without reading a single row
python vfp-documentation-toolkit/tools/dbf_header.py path/to/app/data --recurse
```

Then read the methodology below and work through the stages in order.

## Start here

Read **[`methodology/reverse-engineering-pipeline.md`](methodology/reverse-engineering-pipeline.md)** —
the end-to-end process, stage 0 → 7. Everything else in this repo is a tool or template that
plugs into one of those stages.

**Starting a brand-new job?** Read **[`methodology/next-project-playbook.md`](methodology/next-project-playbook.md)** —
the operational checklist for a new app (scrub → bootstrap → inventory → prove → **port**),
including the decision framework for **porting to a web stack** (Laravel or otherwise), driven by
where the business logic lives and what shape the database is in.

## What's in the box

| Path | Stage | What it is |
|---|---|---|
| [`methodology/reverse-engineering-pipeline.md`](methodology/reverse-engineering-pipeline.md) | all | The spine: the full process, and which tool/artifact belongs to each stage. |
| [`methodology/next-project-playbook.md`](methodology/next-project-playbook.md) | all + port | Operational checklist for a new job, plus the **web-porting decision framework** (when Laravel fits, data/logic migration strategy) and VFP 6 coding traps. |
| [`methodology/conventions.md`](methodology/conventions.md) | 1–2 | House rules for the per-artifact docs (naming, cross-links, structure). |
| [`methodology/VFP-REPORT-CAPTURE-METHODOLOGY.md`](methodology/VFP-REPORT-CAPTURE-METHODOLOGY.md) | 6 | Guide to capturing a VFP app's reports and forms headlessly as a regression baseline. |
| [`skills/document-vfp-artifact/`](skills/document-vfp-artifact/) | 1 | Claude Code skill: turn one FoxBin2PRG text file into a doc. Reads your project's `docs/PROJECT.md` for paths, peer docs, and gotchas (template in `references/project-md-template.md`). Per-type templates under `references/`. |
| [`tools/security/`](tools/security/) | 0 | **Credential scan + scrub + pre-commit hook.** Redact hard-coded credentials before the first commit and block any commit that still leaks one. |
| [`tools/foxparse.py`](tools/foxparse.py) | 1 | Parsers for the FoxBin2PRG text files (`.sc2/.vc2/.fr2/.lb2/.dc2/.db2/.pj2/.mn2`) → structured data (controls, methods, cursors, report bands and objects, menu pads and bars, table schema, DBC integrity). CLI: `python foxparse.py <file or dir> [--summary] [--json out]`. |
| [`tools/dbf_header.py`](tools/dbf_header.py) | 0b / 3 | Header-only DBF metadata reader — schema, row count, size-consistency check for a multi-GB table at the cost of a 2 KB read. Never opens row pages. |
| [`tools/data-conversion/`](tools/data-conversion/) | 0b | Portable DBF→SQLite converter (bundled `dbfread`, Python 3.4 installer included) — mirror a VFP DBC to a queryable SQLite file, even on old XP/Win7 machines. See its `README.txt`. |
| [`tools/dbf.py`](tools/dbf.py), [`tools/dbfscan.py`](tools/dbfscan.py) | 0b / 3 | Self-contained VFP DBF+FPT readers for scripting against the raw tables. `dbfscan.py` compares record counts and key ranges across copies of the data. |
| [`tools/extract_frx.py`](tools/extract_frx.py) | 5 | Extract a `.frx` report's layout as coordinates (the `.frx` is itself a DBF) for high-fidelity re-rendering. |
| [`tools/baseline-capture/`](tools/baseline-capture/) | 6 | PowerShell helpers for a capture harness: `Snap-Window.ps1` (screenshot by HWND, DPI-safe, `-Root` for the whole frame), `Render-EmfPage.ps1` (ReportListener EMF page to PNG), `Watch-Dialogs.ps1` (screenshot, log, and dismiss a VFP process's message boxes and named dialogs). |

## Using it on a new VFP app

Keep each app's docs, fixtures, and app-specific tools in a separate repo of its own (the
methodology calls it the app's **casebook**). This toolkit stays generic and is shared across
all of them.

1. **Scrub credentials FIRST (stage 0).** Before the first `git commit`, run
   [`tools/security/scan_secrets.py`](tools/security/) to locate hard-coded credentials, then
   `scrub_source.py --apply` to redact them, and install the `pre-commit` hook so a fresh
   production pull can never be committed in the clear. (Rotate the real secrets regardless.)
2. **Bootstrap (stage 0).** Run FoxBin2PRG over the app's binaries to get text dumps. Run
   [`tools/data-conversion/`](tools/data-conversion/) over its `data/` folder to get a SQLite mirror;
   use [`tools/dbf_header.py`](tools/dbf_header.py) for an instant header-only table census first.
3. **Inventory (stage 1).** Create `docs/PROJECT.md` in the casebook from
   [`references/project-md-template.md`](skills/document-vfp-artifact/references/project-md-template.md),
   copy the [`document-vfp-artifact`](skills/document-vfp-artifact/) skill into the casebook's
   `.claude/skills/`, then point it at each text file to generate one doc per
   form/class/report/program/table (parse them with [`tools/foxparse.py`](tools/foxparse.py)).
   Follow [`conventions.md`](methodology/conventions.md).
4. **Synthesize → recover → prove (stages 2–6).** Follow the pipeline. Use `dbf.py`/`dbfscan.py`
   for data spelunking, `extract_frx.py` for report layouts, and the capture methodology for a
   regression baseline.

## Known limitations

- **`dbfscan.py` field ranges** only parse ASCII-numeric (`N`) fields; binary `Integer` (`I`)
  fields report `?..?`. Counts are always correct.
- **The capture harness itself is written per app**; only the reusable PowerShell helpers ship
  here. The methodology describes two shapes that have worked: a `.prg` hooked into the app's
  print methods (§1–§11), and a `.prg` that runs the built EXE inside the IDE and drives it from
  `_SCREEN` timers (§12).
- **Parity replay and report renderers are app-specific.** They encode one app's formulas and
  golden output, so you write them in that app's casebook. The pipeline describes what they do.

## Contributing

Issues and pull requests are welcome, especially fixes for FoxBin2PRG output this toolkit
doesn't parse yet, and techniques from your own VFP jobs that belong in the methodology. Please
keep client names, data, and credentials out of anything you submit.

## License

[MIT](LICENSE). The bundled [`dbfread`](tools/data-conversion/dbfread/) library is also MIT
licensed; its notice is in [`tools/data-conversion/dbfread/LICENSE`](tools/data-conversion/dbfread/LICENSE).
The Python installer in `tools/data-conversion/` is distributed under the
[Python Software Foundation License](https://docs.python.org/3/license.html).
