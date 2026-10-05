# The reverse-engineering pipeline

The end-to-end process that turns a legacy Visual FoxPro application into (a) a complete written
spec and (b) executable evidence that the spec is faithful enough to rebuild from.

It was first worked out on a VFP 9 manufacturing app whose pricing and sizing rules lived in
memo fields, then reused on other VFP systems. Results and names from that first app are called
out as *[example]*; substitute your own. The per-artifact docs you produce describe *what the
app is*; this page describes *how you come to know it*, in what order, and which tool produces
each artifact.

> **Why capture this at all.** The per-artifact docs (forms, classes, reports…) record the
> destination. Without this page, the *route* — the bootstrap steps, the tool chain, the order
> of passes, the decisions about what to mine and what to prove — lives only in scattered
> prompts and script headers.

Throughout, the **casebook** is the separate repo you keep for one app's docs, fixtures, and
app-specific tools. This toolkit supplies the process and the generic tools.

---

## The shape of it

```
 stage 0   BOOTSTRAP      binaries -> text dumps        (FoxBin2PRG)
                          data     -> queryable mirror  (DBF -> SQLite)
    |
 stage 1   INVENTORY      one doc per artifact          (subagent per type)
    |
 stage 2   SYNTHESIS      cross-cutting docs: data model, business logic,
    |                     integrations, lifecycle  (second/third pass)
    |
 stage 3   RECOVERY       lift the calculation formulas verbatim
    |
 stage 4   PROOF (logic)  recompute outputs from inputs, diff vs stored  (parity replay)
    |
 stage 5   PROOF (output) extract report layout, re-render, diff vs golden
    |
 stage 6   BASELINE       headless capture of every form + report as a regression set
    |
 stage 7   REBUILD        platform research -> MVP that reproduces the proofs
```

Stages 0–2 are *documentation*. Stages 3–6 are *verification* — they convert "we think we
understand it" into "we can reproduce its outputs from inputs alone," which is what de-risks a
rebuild. Stage 7 consumes all of it.

Each stage below lists its **inputs**, the **tool** that does the work, and the **artifact** it
leaves behind.

---

## Stage 0 — Bootstrap: get the app into readable, queryable form

Before anything is committed, scrub hard-coded credentials with
[`tools/security/`](../tools/security/). Then run two independent extractions. Nothing else can
start until both exist.

### 0a. Binaries → text dumps (FoxBin2PRG)

VFP's real source (`.scx` forms, `.vcx` class libs, `.frx` reports, `.lbx` labels, `.mnx`
menus, `.dbc` database container, `.pjx` project) is stored in **DBF-format binaries** — you
cannot read them in a text editor or diff them. [FoxBin2PRG](https://github.com/fdbozzo/foxbin2prg)
converts each to a deterministic text representation (`.sc2/.vc2/.fr2/.lb2/.mn2/.dc2/.db2/.pj2`).
Native `.prg` programs are already text.

- **Input:** the app's binary source tree.
- **Tool:** FoxBin2PRG, run from the VFP IDE. Errors land in `foxbin2prg_errorlog.ERR`.
- **Artifact:** the `.??2` text dumps, sitting alongside their binaries.
- **Format reference:** how to *read* each dump type is documented in the
  `document-vfp-artifact` skill's [`references/bin2prg-format.md`](../skills/document-vfp-artifact/references/bin2prg-format.md);
  [`tools/foxparse.py`](../tools/foxparse.py) parses them into structured data.

### 0b. Data → queryable SQLite mirror

The runtime `data/` folder is a VFP DBC — a directory of `.dbf`/`.fpt`/`.cdx` files. Mirror it
into a single SQLite file so every later stage can query it with plain SQL (and so the mining
scripts need no VFP runtime).

- **Input:** the app's `data/` folder.
- **Tool:** [`tools/data-conversion/`](../tools/data-conversion/), which can run from a USB stick
  on the client's old XP/Win7 machines with a bundled Python 3.4. Census the tables first with
  [`tools/dbf_header.py`](../tools/dbf_header.py), which reads headers only.
- **Artifact:** a `.sqlite` mirror *[example: ~33 MB]*. **Rebuildable, so don't version-control it.**
- **Note:** memo (`.fpt`) fields can carry the crown jewels. *[example: the formula text that
  stage 3 recovers lived in memo fields, not in the `.prg` code.]*

> **Gotcha:** the mirror is a *clone of the data*, not of the schema semantics. Field names are
> cryptic (`nlouvercou`, `s_frame_ntoprail`); the meaning comes from stages 1–3, not the column
> names.

---

## Stage 1 — Inventory: one document per artifact

Walk the text dumps and produce a written doc for every artifact, filed by type. This is
breadth-first coverage — every form, class, report, program, table gets a page — before any
synthesis.

- **Input:** the stage-0a `.??2` dumps.
- **Tool:** the [`document-vfp-artifact`](../skills/document-vfp-artifact/SKILL.md) skill, copied
  into the casebook's `.claude/skills/`, one invocation per artifact (parallelized with a
  subagent per folder/type). Each type has a template under the skill's `references/`. The house
  rules are [`conventions.md`](conventions.md).
- **Artifact:** numbered doc folders in the casebook (forms, classes, reports, menus, programs,
  and a table catalog under the data model).
- **Per-doc content:** what the artifact does, its controls/members, and **every table it
  touches** — that last list is what makes stage 2 possible.

## Stage 2 — Synthesis: how the pieces work together

A second (and third) pass over the same dumps, now reading *across* artifacts to write the
cross-cutting docs that no single artifact reveals.

- **Inputs:** the stage-1 docs + re-reading the dumps for interactions.
- **Artifacts:**
  - a relationships doc — how the tables join (declared *and* inferred);
  - business-logic docs — pricing, tax, commission, order lifecycle: the domain rules,
    assembled from many forms/programs;
  - integration docs — accounting packages, FTP, web orders, COM helpers;
  - a domain overview and glossary that decode the cryptic names.
- **This is the pass that finds the gaps.** Write them down in an onboarding gap analysis.

---

## Stage 3 — Recovery: lift the calculation formulas verbatim

Find where the rules that turn inputs into outputs actually live, and recover them bug-for-bug.
*[example: they were not in the `.prg` code at all but in `mcalculation` memo fields on rule
tables, executed by the app as VFP expressions.]*

- **Input:** the source dumps, or the memo text in the SQLite mirror.
- **Tool:** direct SQL against the mirror; DBF cross-checks with
  [`tools/dbf.py`](../tools/dbf.py) / [`tools/dbfscan.py`](../tools/dbfscan.py).
- **Artifact:** a recovered-formulas doc in the casebook. **Reproduce the defects on purpose**
  *[example: a misspelling that made the right stile equal the left]* — bug-for-bug parity is
  the goal, with fixes deferred and noted.

## Stage 4 — Proof of logic: parity replay

The pivotal verification. Re-implement the recovered formulas, run them over **historical
inputs**, and diff against the outputs the legacy app **stored** on each row. High match rate =
the engine is genuinely recovered *and* the data is complete enough to drive a rebuild.

- **Input:** the SQLite mirror (inputs + stored outputs on the same rows).
- **Tool:** a replay engine written for the app. It encodes that app's formulas, so it lives in
  the casebook, not here.
- **Artifact:** a parity report and an MVP parity plan.
- *[example result: the 7 deterministic geometry fields reproduced at **97–100%** from inputs
  alone. Operator-editable defaults matched ~40%, which is expected and bounded.]*

> **Precondition — a parity oracle.** This stage only works if the legacy app *persisted* its
> computed outputs. *[example: one product line did (a 53,824-row oracle); another didn't, so it
> was verified by stage-5 output diff instead.]* Check this early: **if outputs weren't stored,
> plan to verify at stage 5/6, not stage 4.**

## Stage 5 — Proof of output: extract layout, re-render, diff the golden

Prove the *printed output* can be reproduced pixel-faithfully in a new stack.

- **Inputs:** the report binary + the SQLite mirror + the app's image assets.
- **Tools:**
  - [`tools/extract_frx.py`](../tools/extract_frx.py) — pull the layout straight from the `.frx`
    (itself a DBF) as coordinates, not re-eyeballed CSS.
  - A renderer for the app's key report (layout + data + images → PDF), compared to a captured
    golden. It encodes that report, so it lives in the casebook.
- **Artifact:** the reconstructed and golden PDFs, side by side.

## Stage 6 — Regression baseline: capture every form + report headlessly

Freeze the legacy app's *observable* behavior — a screenshot per form, a PDF per report, each
tagged with the fixture record that produced it — so the rebuild can be diffed against it later.

- **Input:** the running legacy app + curated fixture records.
- **Tool:** a capture harness written for the app (a VFP program driving each form's own print
  method into a silent PDF printer), plus the PowerShell helpers in
  [`tools/baseline-capture/`](../tools/baseline-capture/). The method is written up in
  [`VFP-REPORT-CAPTURE-METHODOLOGY.md`](VFP-REPORT-CAPTURE-METHODOLOGY.md).
- **Artifact:** `forms/*.png` + `reports/*.pdf`, indexed by a capture log.
- **Key insight:** most VFP reports can't be printed "cold" — they're assembled by their owning
  form's print method. Drive the form in a capture mode, don't call `REPORT FORM` directly.

## Stage 7 — Rebuild: research, then MVP

Everything above feeds the rebuild decision and the MVP that must reproduce the stage-4/5 proofs.

- **Inputs:** all prior artifacts.
- **Artifacts:** a rebuild guide (platform options, data-integration strategy, risk register)
  and an MVP that re-uses the extracted FRX layouts and recovered formulas. The port decision
  itself is covered in [`next-project-playbook.md`](next-project-playbook.md).

---

## The toolchain, at a glance

| Stage | Tool | Runtime |
|---|---|---|
| 0 credential scrub | `tools/security/` | Python 3 |
| 0a binaries→text | FoxBin2PRG | VFP 9 IDE |
| 0b data→SQLite | `tools/data-conversion/`, `tools/dbf_header.py` | Python (3.4 portable / 3.x) |
| 1 inventory | `document-vfp-artifact` skill, `tools/foxparse.py` | Claude Code, Python 3 |
| 3 recovery / audits | `tools/dbf.py`, `tools/dbfscan.py` | Python 3 stdlib |
| 4 parity replay | app-specific (casebook) | your choice |
| 5 layout + render | `tools/extract_frx.py` + an app-specific renderer | Python 3 |
| 6 baseline capture | app-specific harness + `tools/baseline-capture/` | VFP 9 IDE + PowerShell |

## Reusing this on another VFP system

The pipeline is largely project-agnostic; these are the parts to re-scope per system:

1. **Stage 0 is always the same shape** — FoxBin2PRG for source, DBF→SQLite for data. The
   converter and the format reference port directly.
2. **Stage 1 templates** (`document-vfp-artifact/references/`) are per-artifact-*type*, not
   per-app — they carry over. Only `conventions.md` (naming, cross-link style) may need tweaks.
3. **Stages 3–4 depend on where the logic lives.** It may be in memo fields, `.prg` methods, or
   stored procedures. Find the logic's home first, then decide if a parity *oracle* even exists
   (were computed outputs persisted?). No oracle → lean on stage 5/6 output diffing.
4. **Stage 5–6 techniques** (FRX-as-DBF extraction, form-driven headless capture) are generic
   VFP facts and transfer with minimal change.

The reusable order is the durable part: **make it readable and queryable → inventory → synthesize
→ recover the math → prove the math from inputs → prove the output → freeze a baseline → rebuild.**
