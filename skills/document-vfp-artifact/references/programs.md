# Standalone-program template (`.prg` → `08-programs/<name>.md`)

Worked example to mirror: the program peer named in PROJECT.md "Peer docs".
Note that `.prg` files are **native VFP source**, not FoxBin2PRG output — read
them directly.

Many VFP projects accumulate build-time helpers, one-shot patches, dev tools,
and abandoned probes next to the real entry point. **Classify the program's
role up front** and flag dead, build-only, or probe scripts for deletion during
the rebuild. PROJECT.md may already say which programs are on the live call
graph.

After the universal header (see SKILL.md):

```markdown
## Role
One of: runtime entry point | runtime library | build-time helper |
one-shot patch | dev tool | broken/dead probe. Justify in a sentence. Flag
for deletion if not runtime.

## What it does
Step-by-step walkthrough of the top-level flow.

## Key routines
For each PROCEDURE/FUNCTION: signature, body (verbatim if non-trivial),
explanation.

## Inputs / outputs / side effects
Files read/written, tables touched, environment it expects (paths, global
objects, COM objects, DLL declarations, INI or registry keys).

## Called from / calls
What invokes this program (menu, loader, project main file, manual) and
what it invokes.
```

Tips:
- Quote macro substitution (`&var`) and note what it evaluates to.
- `DECLARE ... IN Win32API` blocks are integration points; list every
  declared function and what it is used for.
- `#INCLUDE` lines pull in constants; link the include file so a reader can
  resolve `SOMETHING_LOC` names.
- If the program saves and restores `SET` state, list which settings, because
  a rebuild has to reproduce the environment it assumes.

## Include files (`.h` → `08-programs/<name>.h.md`)
Same header, then **Role** (runtime constants; nothing runs), **Includes**
(what it pulls in and where each path resolves), a **Constants** table with
name, value, designer comment, and *Used by* (a case-sensitive whole-word
grep over every twin, generated program, `.prg`, and the DBC twin, with the
include files themselves excluded), and **Notes**. Call out constants with no
user, `_LOC` strings living outside the localization file, values that must
match table data (user-level names, seek keys), and any compile-time switch
such as a `DEBUGMODE` flag: list every site that reads it and what each one
does, because the value is compiled into everything that includes the file.
