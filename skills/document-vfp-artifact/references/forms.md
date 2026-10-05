# Form template (`.sc2` → `04-forms/<name>.md`)

Worked example to mirror: the form peer named in PROJECT.md "Peer docs". If
there is none yet, this template is the standard.

Read the entire `.sc2` twin first. A form twin is a `DEFINE CLASS` for the form
plus a second for its DataEnvironment; controls appear as flattened dotted
object paths in the property section, and `PROCEDURE`/`ENDPROC` blocks hold
event and method code. Capture the control tree **depth-first** — do not sample.

After the universal header (see SKILL.md), use these sections:

```markdown
## Form metadata
- Base class / parent: ...  (link the class-library doc it inherits from)
- Caption: ...
- Modal: yes/no
- Window state / size / position

## DataEnvironment
| Cursor name | Alias | Source table | Database | Order | Filter |
|---|---|---|---|---|---|

## Controls (depth-first)
For each control:
- **Container path** — `Form.Pageframe1.Page2.Grdgrid1.Column3.Text1`
- **Class:** `textbox` (or the custom class name)
- **Caption / Picture / InputMask:** ...
- **ControlSource:** `orders.order_date` (data binding)
- **Events with code:** Click / Valid / Init / ...
  ```foxpro
  <copy of code body>
  ```
- **Plain-English explanation** of what the code does.

## Form methods (custom)
For each non-inherited method: signature, body, explanation.

## Tables read / written
Bullet list. Mark each as read | write | both.

## Inter-form navigation
Buttons that open other forms; events that broadcast to other controls.
```

Tips:
- Controls of custom classes are defined in a `.vc2` — link to the relevant
  `05-classes/*.md` instead of re-documenting.
- If the form binds to tables, link each to its `03-data-model/tables/*.md`.
- Inherited-but-unchanged methods can be omitted; document **overrides** and
  custom methods, and say which base class supplies the rest.
- Forms that call `REPORT FORM` are the only place a report's table
  dependencies can be determined; record which reports this form prints.
