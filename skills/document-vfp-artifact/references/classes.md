# Class-library template (`.vc2` → `05-classes/<name>.md`)

Worked example to mirror: the class-library peer named in PROJECT.md "Peer
docs". If there is none yet, this template is the standard.

A `.vc2` is **one library that defines many classes**. Document **every**
`DEFINE CLASS` block in the file. **The filename may not reflect contents** —
trust the `DEFINE CLASS ... AS ...` lines, not the file name. PROJECT.md lists
libraries known to be misnamed. State the real contents up front if the name
misleads.

After the universal header (see SKILL.md):

```markdown
## Classes in this library
For each class:

### className (extends parentClass [from somelib.vcx])
- **Purpose:**
- **Custom properties:** name — type — default — meaning
- **Custom methods:** name(params) — returns — purpose
  - **Body:** code + explanation
- **Overridden inherited methods:** name — what changed and why
```

Tips:
- Order classes as they appear, but lead with the most important (the one the
  rest of the app references).
- Quote method bodies verbatim in ` ```foxpro ` fences, then explain.
- Note inheritance crossing libraries (`AS X OF other.vcx`) and link to that
  library's doc. Draw the inheritance chain for framework base classes; a
  form's behaviour is mostly inherited.
- Business-rule methods should link to the relevant `09-business-logic/*.md`
  chapter rather than duplicating the full derivation.
- The `&& comment` after `DEFINE CLASS` in older libraries is the designer's
  one-line description; use it as the starting Purpose, then verify.
