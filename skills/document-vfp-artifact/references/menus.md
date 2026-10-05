# Menu template (`.mn2` → `07-menus/<name>.md`)

Worked example to mirror: the menu peer named in PROJECT.md "Peer docs". If
there is none yet, this template is the standard.

A menu `.mn2` twin is emitted as generated menu code: setup code, `DEFINE PAD`
/ `DEFINE POPUP` / `DEFINE BAR` statements with prompts, key shortcuts, `SKIP
FOR` conditions, and the `ON SELECTION` command or procedure each runs, then
cleanup code.

After the universal header (see SKILL.md):

```markdown
## Menu structure
For each pad → bar, in order:

### Pad: <prompt>  (name)
| Bar | Prompt | Shortcut | Skip For | Action (command / procedure) |
|---|---|---|---|---|

## Setup / cleanup code
Any setup or cleanup blocks and `PROCEDURE`s defined in the menu — quote
verbatim and explain.

## What it launches
Map each non-trivial action to the form/report/program doc it invokes (link).

## Notes
- Which items are admin/utility vs daily-use.
- Items disabled or gated by privilege or application state (the `SKIP FOR`
  expressions say how; quote them).
```

Tips:
- Say whether this menu is the app's primary navigation or a secondary bar
  (PROJECT.md gotchas may say the real workspace is launched elsewhere).
- Menus that attach to `_MSYSMENU` with `MenuLocation` replace or extend the
  system menu; note which, and which pads they remove or reuse.
- Pad names reused from the system menu (`_msm_edit` and friends) are usually
  a placement trick; note it so a rebuilder does not look for edit commands.
