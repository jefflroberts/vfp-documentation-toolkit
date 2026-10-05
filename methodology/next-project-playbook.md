# The next VFP project — engagement playbook

A start-to-finish checklist for taking on a **new** Visual FoxPro app: from the
first safe copy, through documenting and *proving* you understand it, to deciding
**whether and how to port it to a web stack** (Laravel or otherwise). It ties the
toolkit's tools, skill, and pipeline together in the order you actually run them,
and — because the right approach genuinely differs per app — it centers on the two
assessments that drive every later decision: **where the business logic lives** and
**what shape the database is in**.

Read [`reverse-engineering-pipeline.md`](reverse-engineering-pipeline.md) first for
the stage 0→7 spine; this playbook is the operational wrapper around it, plus the
stage-7 **port decision** the pipeline only gestures at.

---

## Calibrate against two real jobs

The method is not one-size-fits-all. These two completed projects bracket the
range, and the differences between them *are* the decision framework:

| | **App A: manufacturing configurator** | **App B: distribution ERP** |
|---|---|---|
| VFP version | 9 | **6** (stricter, quieter — see the trap list below) |
| Domain | Custom manufacturing (geometry/pricing engine) | Wholesale distribution ERP (orders, AR/AP, GL) |
| Where the logic lives | `mcalculation` **memo fields**, `EXECSCRIPT()`-ed at runtime | `.prg` + form methods + framework `.vc2` classes |
| DB integrity | Sparse (one stored proc) | **None** — 0 PK/FK/triggers/validation/procs |
| Parity **oracle**? | **Yes** — computed outputs were persisted per line (53k-row oracle) | **No** — outputs not stored |
| So we proved it by… | **Parity replay** (recompute inputs→outputs, diff stored) — stage 4 | **Output diff + regression baseline** (FRX render, headless capture) — stages 5–6 |
| Extra hazards | Cross-project contamination in a `.vcx` | Hard-coded creds + login backdoor; `custom\` shadows `forms\`; multi-company; invoice-number wrap / 2 GB ceiling |

Two apps, two verification strategies, two port risk profiles — all falling out of
those two rows: **logic location** and **oracle-exists**. Keep them in mind through
every phase.

---

## Phase 0 — Safety & intake (before anything touches git)

1. **Get a sandboxed copy.** Never document or test against live production data
   files. Snapshot the source tree and a *copy* of the data.
2. **Scrub credentials FIRST.** VFP apps embed SMTP/API keys, FTP/SFTP logins, and
   DB passwords as string literals — and sometimes a login backdoor.
   - `python tools/security/scan_secrets.py <src>` — locate them (prints
     `file:line` + kind, never the value).
   - `python tools/security/scrub_source.py <src> --apply` — redact the values in
     place (surgical, line-count-preserving, idempotent).
   - Install the `pre-commit` hook so a later fresh pull can't re-leak.
   - **Rotate the real secrets regardless** — scrubbing the tree doesn't undo past
     exposure, and secrets often also sit in compiled `.exe`s and `custom\`/backup
     copies.
3. **Identify the VFP version.** VFP6 vs 9 changes the coding traps you'll hit when
   you write or run any `.prg` against it (see [VFP6 traps](#vfp6-coding-traps)).
   Check the runtime DLL (`VFP6R.DLL` vs `VFP9R.DLL`).

## Phase 1 — Make it readable & queryable (stage 0)

1. **FoxBin2PRG every binary** → text twins (`.sc2/.vc2/.fr2/.lb2/.dc2/.db2/.pj2`).
   Log what it *couldn't* convert — menus and damaged binaries are common gaps; you
   may have to decode a `.mnx` as a raw DBF (`tools/dbf_header.py` / a DBF reader).
2. **Census the data header-only, before any bulk read.** `python
   tools/dbf_header.py <data-dir> --recurse` gives schema, row counts, size, and a
   size-consistency check for a multi-GB tree at the cost of a few KB. This tells
   you which tables are huge (don't open them casually) and which are empty/dead.
3. **Choose the data-access strategy** (you'll often use all three):
   - **Header-only** (`dbf_header.py`) for schema and inventory.
   - **DBF→SQLite mirror** (`tools/data-conversion/`) for queryable analysis and
     formula recovery — the portable build runs even on the client's old XP/Win7
     box during on-site parity work.
   - **A read-mostly VFP COM bridge** (the app's code wrapped in a VFP COM server) when
     you need the app's *own* functions evaluated (macro-expanded refs,
     `EXECSCRIPT`, compiled-only logic) rather than reimplemented.

## Phase 2 — Inventory & synthesize (stages 1–2)

1. **One doc per artifact.** Either drive the
   [`document-vfp-artifact`](../skills/document-vfp-artifact/) skill per dump, or —
   for a large app (hundreds of forms) — generate skeletons mechanically and have
   agents fill the prose, then gate with verify/check-claims scripts. Parse the
   text twins with [`tools/foxparse.py`](../tools/foxparse.py).
2. **Set conventions up front** ([`conventions.md`](conventions.md)) so the corpus
   is consistent and cross-linked from day one.
3. **Build the cross-references**: call graph, table-usage xref, orphan candidates.
   Remember orphan/unused lists are *candidates, not proof* — `do (var)` /
   `DO FORM (var)` / `USE (var)` resolve at runtime and are invisible to static
   analysis.

## Phase 3 — Locate the business logic (the pivotal assessment)

This is the fork in the road. **Find where the rules actually live**, because it
dictates how you recover them and how you'll prove them:

| Logic lives in… | How to recover it | Example |
|---|---|---|
| `.prg` / form-method source | Read the text twins directly | App B's order/pricing/GL code |
| **Memo fields** `EXECSCRIPT()`-ed at runtime | Pull the memo text from the SQLite mirror **verbatim** | App A's `mcalculation` rules |
| DBC **stored procedures / table triggers** | Parse the `.dc2` container | (rare — check anyway) |
| Compiled-only / heavy `&` macro expansion | Evaluate via the **COM bridge**; you can't read it | scheduler `do (jobname)` patterns |

**Recover it bug-for-bug.** Reproduce the legacy defects on purpose first; note
fixes as deferred. Bug-for-bug parity is the acceptance bar — the recovered
formulas become the rebuild's spec.

## Phase 4 — Assess the database (the other driver)

1. **Integrity — what does the DBC actually enforce?** Parse the `.dc2`
   (`foxparse.parse_dc2`) for PKs, FKs, relations, triggers, field/table rules,
   stored procs. If the answer is "nothing" (as in App B), that is **load-bearing**:
   every invariant is enforced in application code, so the port must *add* the
   constraints the new schema should have — informed by *inferred* relationships,
   not declared ones.
2. **Is there a parity oracle?** Did the app **persist its computed outputs**
   alongside the inputs on the same rows? This single question decides your proof
   strategy (Phase 5). Check it early.
3. **Scale & operational constraints:** table sizes vs VFP's 2 GB per-file ceiling,
   any counter/key wrap, archiving rituals, and **multi-company** folder splits
   (anything recursive touches every company). These become migration requirements.
4. **Data quality:** orphans, free vs DBC tables, width/type conflicts across
   copies, dead/empty tables.

## Phase 5 — Prove you understand it

Pick the proof from the Phase-4 oracle answer:

- **Oracle exists → parity replay (stage 4).** Re-implement the recovered formulas,
  run them over historical inputs, diff against the stored outputs. A high match
  rate proves both the engine *and* that the data is complete enough to rebuild
  from. (App A: 97–100% on the deterministic fields.)
- **No oracle → output diff + baseline (stages 5–6).** Extract report layout from
  the `.frx` (it's a DBF) as coordinates, re-render, and diff a captured golden.
  Then freeze a **headless regression baseline** — a screenshot per form, a PDF per
  report, tagged with the fixture that produced it — as the thing the rebuild is
  measured against. (Key VFP fact: most reports can't print "cold"; drive the
  owning form's print method in a capture mode.)

Either way you now have an **executable definition of correct** to hold the port to.

## Phase 6 — The port decision (Laravel or another web stack)

Only now — with the logic located, the DB assessed, and a proof in hand — decide
the target. The two assessments map directly onto stack fit:

### When a Laravel (or similar server-rendered MVC) port fits well
- **CRUD-heavy business app** over relational-ish data (most ERPs, like App B). The
  tables become Eloquent models; the inferred relationships become real FK
  constraints and `hasMany`/`belongsTo`; the batch `.prg` tools become queued jobs;
  the menu tree becomes routes + policies.
- **Logic is mostly readable procedural code** you can re-express as service/action
  classes. If your Phase-3 answer was "`.prg` methods," porting is transcription +
  tests, not reverse-engineering a black box.
- **Auth is currently menu-only** (`SKIP FOR` gating, bypassable). A web framework's
  real server-side authorization (policies/gates) is a strict upgrade — call it out
  as a security win, not just a port.
- Team is comfortable in PHP; you want batteries-included admin/CRUD velocity.

### When to weigh alternatives
- **Heavy numeric / geometry / rules engine** (App A's sizing math): the *engine*
  is the product. It ports to any language, but favor one with a strong compute and
  testing story and keep the engine as an isolated, parity-tested module regardless
  of the web layer. Node/TS, Python, or C# are all reasonable; the web framework is
  a secondary choice.
- **Report-centric app**: the value is pixel-faithful output. The FRX-extraction →
  render pipeline ports to any stack (server-side PDF), so pick for the render
  ecosystem (e.g. a strong PDF/layout lib) more than the CRUD framework.
- **Desktop-grade interactivity** (grids with instant keyboard-driven entry): a
  request/response web model may degrade the UX operators rely on — consider a
  richer SPA/desktop-web approach for the hot data-entry forms even if the rest is
  server-rendered.

### Data migration strategy (independent of framework)
- **DBF → (SQLite mirror) → MySQL/Postgres.** The SQLite mirror you built in Phase 1
  is a convenient staging point. Handle: code pages / encoding, memo (`M`) and
  general (`G`) fields, date/logical quirks, and the **multi-company folder split**
  (one DB with a company column, or one schema per company — a real decision, not a
  detail).
- **Add the integrity the DBC never had.** Use the Phase-4 *inferred* relationships
  to declare PKs/FKs/uniques in the new schema; validate the legacy data against
  them and quarantine what fails (there will be orphans).

### Logic port strategy
- **Re-implement bug-for-bug first**, gated by the Phase-5 proof, then fix defects
  behind tests. The recovered formulas are the spec; the parity numbers / golden
  reports are the acceptance tests the MVP must reproduce.
- Keep the **COM bridge** alive as a temporary integration seam if you migrate
  incrementally (strangler-fig): stand the new stack up alongside the live app,
  move one module at a time, reconcile against the legacy engine until each module
  is trusted.

## Phase 7 — MVP that reproduces the proofs

The MVP's definition of done is **it reproduces the stage-4/5 artifacts**: the same
parity match rate, the same golden reports, byte- or pixel-close. That's the
non-negotiable acceptance test — everything else (polish, new features) comes after
parity is banked.

---

## VFP6 coding traps

If the app is **VFP6** and you write or run any `.prg` against it (a maintenance
tool, a headless test harness, an extraction probe), these bite — ordered by how
much time they cost:

1. **`[ ]` are string delimiters, not array subscripts.** Use parentheses `a(i,j)`
   for every subscript.
2. **You cannot pass an array via `DO … WITH`.** Use PRIVATE scoping, or (better) a
   cursor.
3. **`;` line-continuations are fragile.** One statement per physical line.
4. **`#DEFINE` shifts runtime line numbers** (breaks `file:line` you rely on for
   error locations). Use memory variables for constants.
5. **`SET DELETED` defaults OFF and silently ruins orphan/purge logic.** `SET
   DELETED ON`, assert it, and test `DELETED()` explicitly.

Also: `SYS(3050)` takes bytes not MB; source must be CRLF; unblock downloaded files
(Mark-of-the-Web); suppress the startup app for headless runs; `RLOCK()` before
`DELETE` in shared mode. A headless compile→run→capture harness (config.fpw with
`SCREEN=OFF`, `SET ALTERNATE` to capture output) lets you test against the real
deployed runtime — but trust error *codes*/proc names, not the cosmetically
scrambled echo under `SCREEN=OFF`.

---

## One-page decision matrix

The whole method collapses to this: read your two assessments off the app, then
read the strategy off the grid.

| Logic location → | in `.prg`/methods | in memo/`EXECSCRIPT` | compiled/macro-only |
|---|---|---|---|
| **Oracle exists** (outputs persisted) | Re-implement from source; **parity replay** to prove | Recover memo verbatim; **parity replay** | Evaluate via COM bridge; **parity replay** |
| **No oracle** | Re-implement from source; **output diff + baseline** | Recover memo verbatim; **output diff + baseline** | COM bridge to reproduce; **baseline** is your only anchor |

And for the port: **readable logic + relational data → server-rendered MVC
(Laravel) is the low-risk default; heavy-compute or pixel-perfect-output apps →
isolate that engine/renderer as a parity-tested module and choose the stack around
it.** Migrate incrementally behind the COM bridge; hold the MVP to the proofs.
