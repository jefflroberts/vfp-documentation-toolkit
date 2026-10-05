# Capturing VFP report baselines headlessly — a reproducible methodology

A project-agnostic guide for producing a **regression baseline of a Visual FoxPro
application's printed reports** (each report rendered to PDF) without human interaction,
so the same reports can be re-rendered against a rebuild and pixel/structurally diffed.

It was distilled from a real VFP 9 manufacturing app built on the CodeMine framework, and
the techniques apply to most VFP form-driven apps. Paths and names from that app are called
out as *[example]*; substitute your own.

---

## 0. The core insight

**You cannot print most reports "cold"** with `REPORT FORM x.frx TO PRINTER`. Real reports
are built and printed by their owning **form's print method**, which first assembles a
work cursor (joins, computed columns, image composites) that the FRX's data environment
binds to. A cold `REPORT FORM` renders blank or errors.

**So: drive the form's own `report()`/print method**, but in a "capture mode" that
suppresses every interactive element (option dialogs, printer pickers, preview windows,
confirm prompts) and redirects output to a silent PDF printer.

A few reports are instead driven by a generic **report-explorer/registry** mechanism
(a table of report definitions + data-build scripts). Those are driven by running the
stored script against a stub parameter object (see §7).

---

## 1. Prerequisites

| Need | Why | Notes |
|---|---|---|
| VFP IDE (e.g. `vfp9.exe`) | Compile + run the harness and forms from source | Runtime-only is not enough |
| The app's source tree | You will edit form methods and regenerate binaries | |
| A silent PDF printer | Reports → PDF with no Save-As dialog | **Bullzip PDF Printer** works well (has a COM API). See §2 |
| A text↔binary tool if editing binary forms | VFP `.scx/.vcx` are binary; edit text dumps and regenerate | **FoxBin2Prg** (see §4) |
| A representative data set | Baselines are only meaningful against realistic records | A clone of production |
| A SQLite (or similar) clone of the data | Cheap ad-hoc querying to pick fixtures and inspect report-registry tables | *[example: `build_appdata_sqlite.py` + `query.py`]* |

---

## 2. Silent PDF printer (Bullzip via its COM API)

Do **not** hand-write Bullzip ini files to a guessed path — the per-user settings folder
varies. Use the COM API, which writes a one-shot "runonce" to the correct auto-located
folder and consumes it after one print job:

```foxpro
oPdf = CREATEOBJECT("Bullzip.PdfSettings")
oPdf.SetValue("Output", m.tcOutFile)     && exact target path for the NEXT print job
oPdf.SetValue("ShowSaveAS", "never")
oPdf.SetValue("ShowSettings", "never")
oPdf.SetValue("ShowPDF", "never")
oPdf.SetValue("ShowProgress", "no")
oPdf.SetValue("ConfirmOverwrite", "no")
oPdf.WriteSettings(.T.)                   && .T. = runonce (auto-located, consumed once)
```

Then print to the named printer: `SET PRINTER TO NAME "Bullzip PDF Printer"` +
`REPORT FORM ... NOCONSOLE TO PRINTER`. Poll for the output file to appear.

To discover the runonce path on a new machine: `New-Object -ComObject Bullzip.PdfSettings`
in PowerShell, `SetValue`/`WriteSettings($true)`, then find the freshly written
`runonce.ini` (on the reference machine it was `%LOCALAPPDATA%\PDF Writer\Bullzip PDF Printer\`).

**.NET-COM report dependencies:** some reports `CREATEOBJECT()` a .NET COM-visible helper
for image composites *[example: an `ImageMaker.ImageAdder` helper that stamps part images onto a ticket]*. Register
it with the 32-bit `RegAsm.exe "...dll" /codebase /tlb` (admin) AND install the matching
.NET runtime (the assembly may target .NET 2.0/3.5; a `0x8013xxxx` OLE error means the CLR
couldn't load). This is also a real deployment dependency, not just a capture concern.

---

## 3. Headless VFP runner

Drive VFP from PowerShell with a private config file so nothing is interactive:

```powershell
# _vfprun.fpw contains:  COMMAND=DO Source\_run_capture.prg
$p = Start-Process vfp9.exe -ArgumentList '-c"<proj>\_vfprun.fpw"' `
       -WorkingDirectory "<proj>" -WindowStyle Minimized -PassThru
Wait-Process -Id $p.Id -Timeout 240        # watchdog
if (-not $p.HasExited) { $p.Kill() }        # a modal/hang blocked it; kill + inspect log
```

- `-WindowStyle Minimized` keeps a stray modal from grabbing the screen; the watchdog kills
  a hung run after the timeout.
- The bootstrap `.prg` (run via the config `COMMAND`) ends with `QUIT` so the IDE exits.
- **Bootstrap must live in the app's source folder** if it `DO`es the app's main program:
  VFP apps often derive their root from `SYS(16,1)` (the outermost program) by walking up
  folder levels — a bootstrap in the wrong folder lands the app root one level off and it
  fails to find its class libraries. *[example: appmain CDs two levels up from SYS(16,1);
  bootstrap in `Source\` so it resolves to the project root.]*
- **CodeMine (and similar frameworks) refuse to run from source until their dev environment
  is initialized.** Call the framework's startup first *[example: `DO C:\codemine\common50\cmStart.PRG`]*
  before booting the app, otherwise you get "...is not installed; you can only run standalone
  EXE files". A custom `-c` config bypasses the IDE's normal startup chaining, so do it explicitly.

The bootstrap pattern: `DO <framework startup>` → set paths/default dir → `DO <capture harness>` → `QUIT`.

---

## 4. Editing binary forms: FoxBin2Prg

`.scx`/`.vcx` are binary. Edit the **text dump** (`.sc2`/`.vc2`) and regenerate:

```foxpro
DO ("...\foxbin2prg.prg") WITH "Source\frmX.sc2", "-TEXT2BIN"   && output name auto-derived
```

- The v1.21 signature is `(inputFile, DIRECTION_FLAG)` — the 2nd arg is `-TEXT2BIN` /
  `-BIN2TEXT` / etc., **NOT** an output filename. Passing a filename errors 1098 but
  FoxBin2Prg swallows it internally — **verify the `.scx` mtime actually changed.**
- The code lives in the `.sct` companion (the `.scx` record structure barely changes).
- Keep a loop that regenerates a list of edited forms; add each form as you hook it.
- The capture **harness `.prg` is interpreted** (`DO`'d) — harness-only edits need no regen.

Edit `.sc2`/`.vc2` files programmatically (Python splice by line number with anchor asserts,
bottom-up for multiple edits) — they are CRLF, tab-indented; author replacement blocks with
explicit tabs. VFP indentation is cosmetic, so exact original whitespace need not be matched.

---

## 5. The capture-mode hook (per driver form)

Signal capture mode out-of-band so it is inert in normal use. Use `_SCREEN` properties —
they **survive `CLEAR ALL`** (which app startup often issues, wiping PUBLIC/LOCAL vars):

```foxpro
llCapture = PEMSTATUS(_SCREEN,"lCaptureReports",5) AND _SCREEN.lCaptureReports
```

In each form's print method, when `llCapture`:
1. **Bypass the options dialog.** Instead of `CREATEOBJECT("frmXreports").Show()`, set the
   print-count variables directly from a `_SCREEN.cCaptureReportKind` signal (which sub-report
   to print). Wrap the original dialog code in the `ELSE`.
2. **Force print, not preview.** Set the method's `lPreview` parameter to `.F.`.
3. **Force a known printer, no chooser.**
   - If the method already has a "named printer from registry" branch, pre-set that registry
     key to the PDF printer from the harness so it takes that branch.
   - If the method hard-codes `TO PRINTER PROMPT` or `SET PRINTER TO GETPRINTER()`, add a
     capture branch: `SET PRINTER TO NAME (_SCREEN.cCapturePrinter)` + `REPORT FORM ... TO
     PRINTER` (drop `PROMPT`).
4. **Guard every interactive call** behind `IF NOT llCapture`: `MESSAGEBOX`, `WAIT WINDOW`
   (no timeout), `confirmync`/`Dialog()` confirmations, and `IF _VFP.STARTMODE = 0 AND
   MESSAGEBOX("Modify report?"...)` (STARTMODE=0 when run from the IDE → fires headless).

The harness opens the form by its **open style** and calls `oForm.report("", .F.)`:
- **order/invoice forms** — resolve the fixture's parent invoice and `OpenForm(scx, invoiceKey
  [, "Open", orderLineKey])` (+`.REQUERY()`).
- **standalone forms** — position the cursor on the fixture record, then `OpenForm(scx)`.

---

## 6. The harness loop

- A catalog maps each report → (driver form, capture-kind, open-style, fixture record).
- Capture must run **inside `READ EVENTS`** (forms only render and release while the event
  loop is live). Pattern: app startup hook detects the `_SCREEN` capture signal, arms a
  one-shot `Timer` on `_SCREEN`, returns `.T.` to enter `READ EVENTS`; the timer runs the
  capture loop then `CLEAR EVENTS`.
- **Resume support:** skip any report whose output PDF already exists (delete to re-capture).
- **Breadcrumbs:** log an `ENTER` row before opening and a `RUNNING` row before calling
  `report()`. A trailing `ENTER`/`RUNNING` with no `OK`/`FAIL` pinpoints exactly where a
  hang or uncatchable crash occurred.
- `SET SAFETY OFF` + `SET BELL OFF` for true headless.

---

## 7. Report-explorer / registry reports (driven without a form)

Some apps store report definitions in a table — *[example: `tblreportexplorer`: `creport`=FRX,
`mcode`=an `EXECSCRIPT` data-build script, `cclass`=a param-panel container class]*. The
script reads filter params from a parameter container (`oContainer`) and builds the cursor.

Drive these **from the harness with no form**: look the row up, then run the script against a
**stub container** that returns "all-data" defaults, then `REPORT FORM`:

```foxpro
SELECT creport, mcode FROM appdata!tblreportexplorer WHERE ctext == m.tcText INTO ARRAY laRep
oStub = CREATEOBJECT("HarnessExpStub")   && combos return "all" sentinels, wide date range
SET STRICTDATE TO 0      && BETWEEN {<<dateval>>} TEXTMERGEs to an ambiguous literal otherwise
SET ENGINEBEHAVIOR 70    && legacy GROUP BY; default 90 → error #1807
= EXECSCRIPT(laRep[1,2], oStub)
REPORT FORM (laRep[1,1]) NOCONSOLE TO PRINTER
```

Build the stub by grepping every `oContainer.<ctrl>` the scripts reference and giving each a
default that means "no filter" (e.g. salesman `getvalue()`→"-1", dealer/product→"%", date
range wide, text/check empty). Restore the SET directives in a **defensive `TRY/CATCH`** — a
restore error must not propagate (it would log a spurious FAIL on a report that succeeded).

---

## 8. Resilience (so one bad report doesn't abort the batch)

- **Type-robust logging.** A CSV-quoting helper must coerce non-character input (missing
  params arrive as `.F.`); otherwise it throws inside the loop's *error handler*, which both
  masks the real error and can surface as an unhandled `#2059`. This single fix is what makes
  catchable report errors log a `FAIL` row and let the batch continue.
- **Catchable vs uncatchable.** Ordinary VFP errors are caught by `TRY/CATCH` and logged.
  **Modal dialogs and hangs are NOT** — they block until the watchdog kills VFP. For those,
  defer the report in the map and move on; re-running resumes past already-captured PDFs.
- **Resume = idempotent.** Each run skips existing outputs, so iterating one report at a time
  is cheap and a killed run loses nothing.

---

## 9. Per-report triage workflow

For each report in your spec:
1. **Grep the source for the FRX name** (`grep -ri "reportname" Source/*.sc2`).
   - **No hit anywhere → the report has no print path** (obsolete/dead). Record and skip.
   - In a form's print method → hook that form (§5).
   - In the report-explorer table only → drive via stub (§7).
2. Identify the print method's interactive elements (options dialog, printer prompt,
   preview branch, confirm/MESSAGEBOX/WAIT) and bypass/guard each (§5).
3. **Grep the form's open path for `SET STEP ON`** — a leftover debug statement drops into
   the IDE debugger and hangs headless. Comment it out.
4. Pick a fixture record that actually exercises the report. Data-gated reports silently
   produce nothing if the data isn't present *[example: a measurement-invoice only prints
   when `nmeasureamount<>0`]* — query the data to choose a record that has it.
5. Run headless; read the breadcrumb log; fix the first failure; repeat.

---

## 10. Error/symptom cheat-sheet

| Symptom | Cause | Fix |
|---|---|---|
| "...is not installed; run standalone EXE only" | Framework dev env not initialized | Run framework startup *[cmStart]* before the app |
| `File 'X\appmain.vcx' does not exist` (wrong dir) | Bootstrap not in `Source\`; app root math off | Move bootstrap into the source folder |
| Runtime "Syntax error" at a `var=a : var=b` line | VFP has **no `:` statement separator** | One statement per line |
| Hang on form open, no error | Leftover `SET STEP ON` (or a modal) | Comment it / guard with `NOT llCapture` |
| `#1733`/`class not found` on `CREATEOBJECT` | .NET-COM report helper unregistered | `RegAsm /codebase /tlb` |
| `0x80131700` OLE error | Wrong/absent .NET CLR for the helper | Install the targeted .NET runtime |
| `#2032 Ambiguous date` | `{<<date>>}` merged to `{mm/dd/yyyy}` | `SET STRICTDATE TO 0` around the EXECSCRIPT |
| `#1807 GROUP BY missing/invalid` | Strict SQL mode | `SET ENGINEBEHAVIOR 70` |
| `#11 Function argument...` in the log writer | CSV helper got a non-string (missing param) | Make the helper type-robust |
| Unhandled `#2059` at a loop boundary | An error escaped because the error *handler itself* crashed | Fix the handler (usually the same type-robustness bug) |
| "file exists, overwrite?" prompt | `SET SAFETY ON` | `SET SAFETY OFF` in the harness |
| Report opens but renders blank/old data | Cold `REPORT FORM`; the form builds the cursor | Drive the form's print method instead |
| A report's FRX references a field the cursor lacks | App data/report mismatch (pre-existing bug) | Out of scope for capture; record it |

---

## 11. What "done" looks like / honest limits

Expect to capture the **operationally important paperwork** (orders, invoices, tickets,
labels) and the parameterized management reports. Expect a tail you **cannot** capture without
fixing the app or the data:
- reports with **no print path** in the current source (obsolete entries in the spec);
- reports gated on **data your fixtures lack**;
- reports with **pre-existing app bugs** (a report bound to a cursor missing a field);
- reports reached only through **forms that hang/modal** in ways that need interactive
  debugging.

Record each of these explicitly with its reason — that list is itself a useful audit of the
legacy app. *[example: the first app captured 19 of 30; the other 11 were dead reports, data-gated,
app bugs, or hangs, each written up with its reason.]*

---

## 12. Forms as screenshots, driven from inside the running EXE (Tastrade, 2026-09)

The sections above capture *reports* by editing the app's forms. On Tastrade the
whole application, forms and reports, was captured **without touching its source**,
by running the built EXE inside a VFP 9 IDE session and driving it from timers.
What held, and what did not:

- **`DO app.exe` from the IDE runs the compiled EXE's own code.** Its `SYS(16)`-based
  root-finding worked unchanged (`CURDIR()` was the app root). The harness is a
  `.prg` named by a config file (`vfp9.exe -c"capture.fpw"`, `COMMAND=DO capture.prg
  WITH ...`); it arms two timers on `_SCREEN` (`AddObject`), stores its helper object
  in a `_SCREEN` property (`AddProperty`), then `DO`es the EXE. Classes defined in the
  harness `.prg` stay available because the `.prg` stays on the call stack, and the
  app's `SET PROCEDURE` and `SET CLASSLIB` do not disturb the objects. Its closing
  `RELEASE ALL EXTENDED` / `CLEAR ALL` **does**: after the EXE returned, the `_SCREEN`
  property holding the helper was gone ("Unknown member") and so were the harness's
  own variables. Do everything before `CLEAR EVENTS`; after the `DO` returns, only
  `ON ERROR`, `ON SHUTDOWN`, `QUIT`.
- **Timers fire inside modal `Show()`**: the intro form, `DO FORM x` with
  `WindowType = 1`, and `CREATEOBJECT(...).Show()` dialogs were all captured and closed
  by a 400 ms "sentinel" timer that watches `_SCREEN.ActiveForm.WindowType`. They did
  **not** fire reliably inside a modal form opened by a report's data environment
  `Init` while `REPORT FORM` runs (one of two such dialogs was reached). Those are
  dismissed from outside: the runner finds the child window by title, snapshots it,
  and sends Enter (OK is the default button).
- **Message boxes need an outside watcher.** `MESSAGEBOX()` and VFP's own error dialog
  are `#32770` windows. On Windows 11 (26200) `FindWindowEx(NULL, ..., "#32770")` found
  none of them and `FindWindowEx` by child class stopped after the first `Static`;
  `EnumWindows` and `EnumChildWindows` with callbacks work (`Watch-Dialogs.ps1`). Press
  **Ignore** when it exists (a form's `Error` method with `MB_ABORTRETRYIGNORE`, or VFP's
  Cancel/Suspend/Ignore), else OK, No, Cancel. Abort under a `DEBUGMODE` build does
  `SUSPEND`, which stops the run.
- **`ON ERROR` in the harness returns into the app**, so an untrapped error logs and the
  next line runs; a form's own `Error` method still takes precedence for errors inside
  its methods, which is where the message boxes come from. Both records together
  (harness log and dialog log) are the evidence.
- **`_SCREEN.HWnd` is the MDI client.** `PrintWindow` on it gives the client area only;
  `GetAncestor(hwnd, GA_ROOT)` gives the frame with title bar, menu bar, docked
  toolbars, and status bar (`Snap-Window.ps1 -Root`). `PrintWindow` with
  `PW_RENDERFULLCONTENT` captured child forms completely even where the main window
  extended past the physical screen.
- **DPI.** On a 200% desktop a DPI-aware caller measures a VFP window at twice its
  pixels and `PrintWindow` renders the upscaled bitmap. Set the thread to
  `DPI_AWARENESS_CONTEXT_UNAWARE` first; the window is then captured at its own pixel
  size (`Snap-Window.ps1` does this always).
- **`ReportListener.OutputPage` to PNG (device type 104) was half-size and clipped**
  (408 by 528 for Letter, whatever `nWidth`/`nHeight` were passed) on the same desktop;
  EMF (device type 100) was the full page as vectors. Render the EMF with
  `Render-EmfPage.ps1` at any scale. `ListenerType = 3` renders every page with no
  printer or preview; `PageTotal` gives the count.
- **Under `-c` config start-up the IDE's Standard toolbar became visible after the
  `COMMAND` program had started**, so an app that hides VFP toolbars by name at its own
  start-up missed it; hide them in the harness before `DO`ing the EXE (the runtime has
  none).
- **Protected properties** cannot be read from the timer (`PEMSTATUS` says they exist;
  reading them errors). Test readiness by public state (`TYPE("oApp") = "O"`,
  `_SCREEN.FormCount`).
- **A low-level `FCREATE` log is unreadable by other processes until closed**; copy it
  after the run, and make the runner's own CSV the live progress signal. Write a marker
  file when the capture sequence ends and another after `QUIT`, so the watchdog can
  tell "still shutting down" from "hung".
- **An `.scx` form's `Class` is its parent class; its own name is `Name`.** Key any
  per-form dismiss logic on `Name`.
- **A second pass that enters data** reuses the same harness with scenario steps: set a
  control's `Value` with focus on it and call the form's own `Save()`, so the app's
  `WriteBuffer`, rules, and `Error` method run as they would for a user; do table work
  a form would do through `SET DATASESSION TO form.DataSessionId` + `EXECSCRIPT`; write
  an answer file before an action whose dialog needs a specific button (`Yes` on a
  delete that the RI trigger will refuse) and let the watcher consume it. Choose every
  scenario so that it ends in a refusal or a `Restore()`, and diff the data files
  against the committed ones afterwards (a header stamp is three bytes; an ID counter
  that advanced is a finding, not an accident). Compare strings with `==` in the
  dispatch: with `SET EXACT OFF`, `"chngpswd-empty" = "chngpswd"` is true. A credit
  check that reads saved rows only cannot be tripped by the order being saved; find
  a customer already over the limit in the data instead.
- **What the run found that reading had not** (the point of stage 6): the VFP 9 rebuild
  raises `1807 SQL: GROUP BY clause is missing or invalid` in a stored procedure and a
  view written for VFP 7's engine (`SET ENGINEBEHAVIOR 70`), so two of the nine
  non-modal forms fail on open under VFP 9's default 90. Nothing in the source says so;
  the twins are the same text either way. A second capture with the harness forcing
  `SET ENGINEBEHAVIOR 70` isolates the upgrade's effect from the sample's own defects.
