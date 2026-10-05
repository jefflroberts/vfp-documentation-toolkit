"""
Parsers for FoxBin2PRG text representations of Visual FoxPro binaries.

Formats handled
---------------
.sc2 / .vc2   PRG-like:  DEFINE CLASS .. ADD OBJECT .. PROCEDURE .. ENDDEFINE
.fr2 / .lb2   record-like: <Reportes attr=".." > <tag><![CDATA[..]]> </Reportes>
.dc2 / .db2   XML-ish:   <DATABASE><TABLES><TABLE>..  /  <TABLE><FIELDS><FIELD>..
.pj2          PRG-like:  .ADD('path')  && *< FileMetadata: Type=".." />
.mn2          generated menu code between *<MenuCode> .. *</MenuCode> markers

Notes discovered empirically across VFP 6/9 codebases (verify per project):
  * Every .sc2 holds exactly two DEFINE CLASS blocks: the form, and its
    dataenvironment.  Nested controls are flattened into dotted ObjPaths
    ('b_grid.desc.Header1'), not nested class blocks.
  * FRX objtype: 1=printer setup, 5=label, 6=line, 7=rectangle, 8=field
    expression, 9=band, 17=picture, 18=report variable, 23=font resource,
    25=dataenvironment.
  * Reports MAY declare cursors: objtype 26 records under the objtype 25
    dataenvironment (Tastrade: 12 of 13 do, opening DBC views). A report with
    no cursor renders against aliases left open by the caller, so table usage
    comes from its cursors plus alias.field references plus the caller.
  * Band objcode is 0=Title 1=Page Header ... 8=Summary (see BAND); object
    vpos includes one designer band bar (BAND_BAR) per preceding band.
"""
import os
import re

# --------------------------------------------------------------------------
# shared
# --------------------------------------------------------------------------

def read(path):
    with open(path, "r", encoding="latin-1") as f:
        return f.read()


# VFP commands that name a table/alias directly.
_SQL_FROM = re.compile(r"\bFROM\s+([A-Za-z_]\w*)", re.I)
_SQL_JOIN = re.compile(r"\bJOIN\s+([A-Za-z_]\w*)", re.I)
_SQL_INTO = re.compile(r"\bINTO\s+(?:TABLE|CURSOR)\s+([A-Za-z_]\w*)", re.I)
_CREATE = re.compile(r"\bCREATE\s+(?:CURSOR|TABLE)\s+([A-Za-z_]\w*)", re.I)
_SQL_INS = re.compile(r"\bINSERT\s+INTO\s+([A-Za-z_]\w*)", re.I)
_SQL_UPD = re.compile(r"\bUPDATE\s+([A-Za-z_]\w*)", re.I)
_SQL_DEL = re.compile(r"\bDELETE\s+FROM\s+([A-Za-z_]\w*)", re.I)
_USE = re.compile(r"^\s*USE\s+([A-Za-z_]\w*)", re.I | re.M)
_SELECT_ALIAS = re.compile(r"^\s*SELECT\s+([A-Za-z_]\w*)\s*$", re.I | re.M)
_ALIAS_FIELD = re.compile(r"\b([a-zA-Z_]\w*)\s*\.\s*[a-zA-Z_]\w*")

# words that look like aliases but are language/objects, not tables
_NOT_TABLES = {
    "thisform", "this", "thisapp", "_screen", "_vfp", "parent", "sys", "m",
    "dodefault", "screen", "form", "control", "value", "caption", "left",
    "top", "width", "height", "name", "alias", "distinct", "all", "max", "min",
    "count", "sum", "avg", "iif", "alltrim", "trim", "upper", "lower", "str",
    "val", "date", "datetime", "recno", "reccount", "deleted", "empty", "len",
    "space", "padl", "padr", "substr", "at", "occurs", "type", "vartype",
}


def tables_from_code(code):
    """Table/alias names referenced by SQL, USE, or SELECT <alias> in VFP code."""
    found = set()
    for rx in (_SQL_FROM, _SQL_JOIN, _SQL_INS, _SQL_UPD, _SQL_DEL, _USE, _SELECT_ALIAS):
        found |= {m.lower() for m in rx.findall(code)}
    found -= _NOT_TABLES
    return sorted(found)


# Visual FoxPro allows PROCEDURE and FUNCTION to be abbreviated to any prefix of at
# least four characters -- `proc removealocs` is legal and common. Matching only the
# full keywords can miss ~⅓ of definitions in a real codebase (observed 36 of 114 in
# one library), so honour the abbreviations.
PROC_DEF = re.compile(
    r"^[ \t]*(?:PROC(?:E(?:D(?:U(?:RE?)?)?)?)?|FUNC(?:T(?:I(?:O(?:N)?)?)?)?)\s+(\w+)",
    re.I | re.M)


def procedures_in(code):
    """Names of procedures/functions defined in a .prg, honouring VFP abbreviations."""
    seen, out = set(), []
    for name in PROC_DEF.findall(code):
        low = name.lower()
        if low not in seen:
            seen.add(low)
            out.append(name)
    return out


def cursors_from_code(code):
    """Temp cursors the code CREATES (INTO CURSOR/TABLE, CREATE CURSOR/TABLE).
    These are outputs/scratch, not persistent tables, and must not be reported as
    tables the form 'uses' -- otherwise every scratch alias looks like a real table."""
    made = {m.lower() for m in _SQL_INTO.findall(code)}
    made |= {m.lower() for m in _CREATE.findall(code)}
    return sorted(made - _NOT_TABLES)


def aliases_from_expr(expr):
    """alias.field references inside a report/label expression."""
    return sorted({m.lower() for m in _ALIAS_FIELD.findall(expr)} - _NOT_TABLES)


# --------------------------------------------------------------------------
# .sc2 / .vc2  (forms and class libraries)
# --------------------------------------------------------------------------

# Trailing "&& comment" after the parent/OF clause is allowed: VFP 6/7 era
# libraries (e.g. Microsoft's Tastrade sample) annotate every DEFINE CLASS.
_DEFCLASS = re.compile(
    r'^DEFINE\s+CLASS\s+([\w]+)\s+AS\s+([\w.]+)(?:\s+OF\s+"?([^"\r\n&]+?)"?)?'
    r'\s*(?:&&.*)?$',
    re.I | re.M)
_ADDOBJ = re.compile(
    r"^\s*ADD\s+OBJECT\s+'([^']+)'\s+AS\s+([\w.]+)(?:\s+OF\s+\"?([^\"\r\n,;]+?)\"?)?\s+WITH\s*;?\s*$",
    re.I | re.M)
_ENDOBJ = re.compile(r'\*<\s*END OBJECT:\s*ClassLib="([^"]*)"\s+BaseClass="([^"]*)"')
# FoxBin2PRG indents PROCEDURE/ENDPROC one tab inside DEFINE CLASS -- anchoring at
# column 0 silently yields zero methods for every form.
# PROTECTED/HIDDEN prefixes and a trailing "&& comment" are both common in
# VFP 6/7 era class libraries; the Tastrade sample uses both on 44 methods.
_PROC = re.compile(r"^[ \t]*(?:(?:PROTECTED|HIDDEN)\s+)?PROCEDURE\s+([\w.]+)\s*(?:&&.*)?$",
                   re.I | re.M)
_ENDPROC = re.compile(r"^[ \t]*ENDPROC\s*$", re.I | re.M)
_PROP = re.compile(r"^\s*([\w.]+)\s*=\s*(.+?),?\s*;?\s*$")

# control properties worth surfacing in documentation
KEY_PROPS = ("caption", "controlsource", "rowsource", "rowsourcetype", "value",
             "recordsource", "tooltiptext", "enabled", "visible", "readonly",
             "inputmask", "format", "picture", "boundcolumn", "columncount")


def _split_classes(text):
    """Yield (name, parent, classlib, body) for each DEFINE CLASS .. ENDDEFINE."""
    matches = list(_DEFCLASS.finditer(text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        stop = re.search(r"^ENDDEFINE\s*$", body, re.I | re.M)
        if stop:
            body = body[:stop.start()]
        yield m.group(1), m.group(2), (m.group(3) or "").strip(), body


def _parse_with_block(body, start):
    """Read the `prop = value, ;` lines following an ADD OBJECT .. WITH."""
    props, i = {}, start
    lines = body.splitlines()
    while i < len(lines):
        line = lines[i]
        if _ENDOBJ.search(line):
            break
        if re.match(r"^\s*(ADD\s+OBJECT|PROCEDURE|ENDDEFINE)\b", line, re.I):
            break
        m = _PROP.match(line)
        if m:
            props[m.group(1).lower()] = m.group(2).strip().rstrip(",").strip()
        i += 1
        # The WITH block is a `;`-continued statement; the first line that does not
        # continue is its last property line.
        if m and not line.rstrip().endswith(";"):
            break
    return props, i


def _parse_methods(body):
    """PROCEDURE <obj>.<event> .. ENDPROC -> {name: code}"""
    out = {}
    for m in _PROC.finditer(body):
        end = _ENDPROC.search(body, m.end())
        code = body[m.end():end.start()] if end else body[m.end():]
        code = code.strip("\r\n")
        if code.strip():
            out[m.group(1)] = code
    return out


def _parse_controls(body):
    controls = []
    lines = body.splitlines()
    for idx, line in enumerate(lines):
        m = _ADDOBJ.match(line)
        if not m:
            continue
        props, _ = _parse_with_block(body, idx + 1)
        # ClassLib/BaseClass live in the trailing END OBJECT comment
        classlib, baseclass = m.group(3) or "", ""
        tail = "\n".join(lines[idx:idx + 60])
        e = _ENDOBJ.search(tail)
        if e:
            classlib = e.group(1) or classlib
            baseclass = e.group(2)
        path = m.group(1)
        controls.append({
            "name": path.split(".")[-1],
            "path": path,
            "depth": path.count("."),
            "parent": ".".join(path.split(".")[:-1]) or None,
            "class": m.group(2),
            "classlib": classlib,
            "baseclass": baseclass,
            "props": {k: v for k, v in props.items() if k in KEY_PROPS},
        })
    return controls


def _parse_cursors(body):
    cursors = []
    lines = body.splitlines()
    for idx, line in enumerate(lines):
        m = _ADDOBJ.match(line)
        if not m or m.group(2).lower() != "cursor":
            continue
        props, _ = _parse_with_block(body, idx + 1)
        clean = lambda v: (v or "").strip().strip('"').strip()  # noqa: E731
        cursors.append({
            "object": m.group(1),
            "alias": clean(props.get("alias")),
            "table": clean(props.get("cursorsource")),
            "database": clean(props.get("database")),
            "order": clean(props.get("order")),
            "filter": clean(props.get("filter")),
        })
    return cursors


def parse_sc2(path, known_tables=None):
    """known_tables: set of real table names (from data01 + free tables). When given,
    names found in code are split into real tables vs scratch cursors instead of
    being reported wholesale."""
    text = read(path)
    classes = list(_split_classes(text))
    form = next((c for c in classes if c[1].lower() != "dataenvironment"), None)
    de = next((c for c in classes if c[1].lower() == "dataenvironment"), None)

    controls = _parse_controls(form[3]) if form else []
    methods = _parse_methods(form[3]) if form else {}
    cursors = _parse_cursors(de[3]) if de else []

    all_code = "\n".join(methods.values())
    de_tables = {c["table"].lower() for c in cursors if c["table"]}
    control_tables = set()
    for c in controls:
        cs = c["props"].get("controlsource", "").strip('"')
        if "." in cs:
            control_tables.add(cs.split(".")[0].lower())

    code_tables = set(tables_from_code(all_code))
    created = set(cursors_from_code(all_code))

    code_only = code_tables - de_tables - created
    if known_tables is not None:
        real = {t for t in code_only if t in known_tables}
        scratch = code_only - real
    else:
        real, scratch = code_only, set()

    return {
        "file": os.path.basename(path),
        "path": path,
        "name": form[0] if form else None,
        "parentclass": form[1] if form else None,
        "classlib": form[2] if form else None,
        "control_count": len(controls),
        "controls": controls,
        "cursors": cursors,
        "methods": {k: v for k, v in methods.items()},
        "method_count": len(methods),
        "code_lines": sum(len(v.splitlines()) for v in methods.values()),
        "tables": {
            "dataenvironment": sorted(de_tables),
            "controlsource": sorted(control_tables - de_tables),
            "code": sorted(real),
            "created_cursors": sorted(created),
            "unresolved_aliases": sorted(scratch),
        },
        "calls_reports": sorted({m.lower() for m in re.findall(
            r"REPORT\s+FORM\s+([\w\\/.]+)", all_code, re.I)}),
        "calls_forms": sorted({m.lower() for m in re.findall(
            r"DO\s+FORM\s+([\w\\/.]+)", all_code, re.I)}),
    }


def parse_vc2(path):
    """A class library: every DEFINE CLASS is a reusable class."""
    text = read(path)
    out = []
    for name, parent, lib, body in _split_classes(text):
        if parent.lower() == "dataenvironment":
            continue
        methods = _parse_methods(body)
        out.append({
            "name": name,
            "parentclass": parent,
            "classlib": lib,
            "controls": _parse_controls(body),
            "methods": methods,
            "method_count": len(methods),
            "code_lines": sum(len(v.splitlines()) for v in methods.values()),
        })
    return {"file": os.path.basename(path), "path": path,
            "class_count": len(out), "classes": out}


# --------------------------------------------------------------------------
# .fr2 / .lb2  (reports and labels)
# --------------------------------------------------------------------------

OBJTYPE = {
    1: "printer setup", 5: "label", 6: "line", 7: "rectangle",
    8: "field expression", 9: "band", 10: "designer metadata", 17: "picture",
    18: "report variable", 23: "font resource", 25: "dataenvironment",
    26: "cursor",
}
# Band records (objtype 9) carry the band kind in objcode. VFP always writes
# Page Header, Detail and Page Footer; Title, Summary, group and column bands
# only when used. A three-band report is therefore objcode 1/4/7, never 1/2/3.
BAND = {0: "Title", 1: "Page Header", 2: "Column Header", 3: "Group Header",
        4: "Detail", 5: "Group Footer", 6: "Column Footer", 7: "Page Footer",
        8: "Summary", 9: "Detail Header", 10: "Detail Footer"}
# Object vpos values are designer coordinates: each band's content is followed
# by the band's title bar, BAND_SEPARATOR_HEIGHT_FRUS in ffc/_frxcursor.h.
# Band k therefore starts at sum(height[:k]) + k * BAND_BAR.
BAND_BAR = 2083.333
TOTALTYPE = {0: "", 1: "Count", 2: "Sum", 3: "Average", 4: "Lowest",
             5: "Highest", 6: "Std deviation", 7: "Variance"}
_LAYOUT_OBJECTS = (5, 6, 7, 8, 17)

# Attribute values FoxBin2PRG writes for an untouched property; anything else
# is a designer choice worth keeping in the record's "props".
_FR_DEFAULT = {
    "platform": "WINDOWS ", "uniqueid": "", "timestamp": "0", "name": "",
    "order": "", "unique": ".F.", "environ": ".F.", "boxchar": " ",
    "fillchar": " ", "pengreen": "0", "penblue": "0", "fillred": "0",
    "fillgreen": "0", "fillblue": "0", "pensize": "0", "penpat": "0",
    "fillpat": "0", "fontface": "", "fontstyle": "0", "fontsize": "0",
    "mode": "0", "ruler": "0", "rulerlines": "0", "grid": ".F.", "gridv": "0",
    "gridh": "0", "float": ".F.", "stretch": ".F.", "stretchtop": ".F.",
    "top": ".F.", "bottom": ".F.", "suptype": "0", "suprest": "0",
    "norepeat": ".F.", "resetrpt": "0", "pagebreak": ".F.", "colbreak": ".F.",
    "resetpage": ".F.", "general": "0", "spacing": "0", "double": ".F.",
    "swapheader": ".F.", "swapfooter": ".F.", "ejectbefor": ".F.",
    "ejectafter": ".F.", "plain": ".F.", "summary": ".F.", "addalias": ".F.",
    "offset": "0", "topmargin": "0", "botmargin": "0", "totaltype": "0",
    "resettotal": "0", "resoid": "0", "curpos": ".F.", "supalways": ".F.",
    "supovflow": ".F.", "suprpcol": "0", "supgroup": "0", "supvalchng": ".F.",
}

_REC = re.compile(r"<Reportes\s(.*?)</Reportes>", re.S)
_ATTR = re.compile(r'(\w+)="([^"]*)"')
_CDATA = re.compile(r"<(\w+)><!\[CDATA\[(.*?)\]\]>", re.S)
_PROPLINE = re.compile(r"^\s*(\w+)\s*=\s*(.*?)\s*$", re.M)
_DEVNAMES = re.compile(r"\{1\}\{0\}(.*?)\{0\}(.*?)\{0\}(.*?)\{0\}")


def reset_name(code):
    """Calculate 'Reset on' code. 1-3 are fixed; groups start at 6 (inferred:
    the Tastrade invoice subtotal, reset per order, carries 6)."""
    fixed = {0: "", 1: "End of report", 2: "End of page", 3: "End of column"}
    if code in fixed:
        return fixed[code]
    return "Group %d" % (code - 5) if code >= 6 else "code %d" % code


def _props_block(text):
    """'Name = value' lines (DE and cursor records) -> dict, lowercase keys."""
    return {k.lower(): v.strip('"') for k, v in _PROPLINE.findall(text)}


def _methods(code):
    """PROCEDURE name ... ENDPROC blocks in DE code -> {name: body}."""
    out = {}
    for m in re.finditer(r"^\s*PROCEDURE\s+(\w+)\s*$(.*?)^\s*ENDPROC", code, re.S | re.M | re.I):
        out[m.group(1)] = m.group(2).strip("\r\n")
    return out


def parse_fr2(path):
    text = read(path)
    recs = []
    for m in _REC.finditer(text):
        blk = m.group(1)
        attrs = dict(_ATTR.findall(blk.split(">", 1)[0]))
        cdata = {k: v.strip() for k, v in _CDATA.findall(blk)}
        ot = int(attrs.get("objtype", 0) or 0)
        oc = int(attrs.get("objcode", 0) or 0)
        props = {k: v for k, v in attrs.items()
                 if k not in ("objtype", "objcode", "vpos", "hpos", "height", "width")
                 and _FR_DEFAULT.get(k) != v}
        recs.append({
            "objtype": ot, "kind": OBJTYPE.get(ot, "objtype %d" % ot),
            "objcode": oc, "name": attrs.get("name", "").strip(),
            "vpos": float(attrs.get("vpos", 0) or 0), "hpos": float(attrs.get("hpos", 0) or 0),
            "height": float(attrs.get("height", 0) or 0), "width": float(attrs.get("width", 0) or 0),
            "expr": cdata.get("expr", ""), "supexpr": cdata.get("supexpr", ""),
            "picture": cdata.get("picture", ""), "comment": cdata.get("comment", ""),
            "tag": cdata.get("tag", ""), "style": cdata.get("style", ""),
            "penred": cdata.get("penred", "0"), "props": props, "band": None,
        })

    # -- bands: file order is layout order; number groups, pair footers ------
    band_recs = [r for r in recs if r["objtype"] == 9]
    n_groups = sum(1 for r in band_recs if r["objcode"] == 3)
    gh = gf = 0
    y = 0.0
    bands = []
    for r in band_recs:
        label = BAND.get(r["objcode"], "band code %d" % r["objcode"])
        if r["objcode"] == 3:
            gh += 1; label = "Group Header %d" % gh
        elif r["objcode"] == 5:
            gf += 1; label = "Group Footer %d" % (n_groups - gf + 1)
        r["band"] = label
        bands.append({"band": label, "objcode": r["objcode"], "height": r["height"],
                      "start": y, "group_expr": r["expr"] if r["objcode"] == 3 else "",
                      "props": r["props"], "objects": []})
        y += r["height"] + BAND_BAR
    for r in recs:
        if r["objtype"] in _LAYOUT_OBJECTS and bands:
            # an object can never sit on a band bar, so anything below the end of
            # band i-1's content belongs to band i (bar height varies by VFP version)
            k = max(i for i, b in enumerate(bands)
                    if i == 0 or bands[i - 1]["start"] + bands[i - 1]["height"] + 5 <= r["vpos"])
            r["band"] = bands[k]["band"]
            bands[k]["objects"].append(r)
    for b in bands:
        b["objects"].sort(key=lambda r: (r["vpos"], r["hpos"]))

    fields = [r for r in recs if r["objtype"] == 8 and r["expr"]]
    labels = [r for r in recs if r["objtype"] == 5 and r["expr"]]
    variables = [{"name": r["name"], "expr": r["expr"], "initial": r["tag"],
                  "calculate": TOTALTYPE.get(int(r["props"].get("totaltype", 0)), ""),
                  "reset": reset_name(int(r["props"].get("resettotal", 0))),
                  "release_after_report": r["props"].get("unique") == ".T."}
                 for r in recs if r["objtype"] == 18]
    groups = [b["group_expr"] for b in bands if b["group_expr"]]

    aliases = set()
    for r in fields:
        aliases |= set(aliases_from_expr(r["expr"]))
    for v in variables:
        aliases |= set(aliases_from_expr(v["expr"]))

    # -- printer environment: expr is the readable form, tag the DEVNAMES ----
    prn = next((r for r in recs if r["objtype"] == 1), None)
    printer = {}
    if prn:
        for line in prn["expr"].splitlines():
            if "=" in line:
                k, v = line.split("=", 1); printer[k.strip().upper()] = v.strip()
        dn = _DEVNAMES.search(prn["tag"])
        if dn:
            printer["DEVNAMES"] = {"driver": dn.group(1), "device": dn.group(2), "output": dn.group(3)}
    orient = printer.get("ORIENTATION")

    # -- data environment and its cursors (objtype 25 / 26) -------------------
    de = next((r for r in recs if r["objtype"] == 25), None)
    de_props = _props_block(de["expr"]) if de else {}
    de_code = de["tag"] if de else ""
    cursors = []
    for r in recs:
        if r["objtype"] == 26:
            p = _props_block(r["expr"])
            cursors.append({"object": p.get("name", ""), "alias": p.get("alias", ""),
                            "table": p.get("cursorsource", ""), "database": p.get("database", ""),
                            "filter": p.get("filter", ""), "order": p.get("order", "")})

    return {
        "file": os.path.basename(path), "path": path,
        "record_count": len(recs),
        "field_count": len(fields), "label_count": len(labels),
        "fields": [r["expr"] for r in fields],
        "labels": [r["expr"].strip('"') for r in labels],
        "variables": variables,
        "bands": bands,
        "group_expressions": groups,
        "suppression_rules": sorted({r["supexpr"] for r in recs if r["supexpr"]}),
        "images": sorted({r["picture"].strip('"') for r in recs if r["objtype"] == 17 and r["picture"]}),
        "referenced_aliases": sorted(aliases),
        "cursors": cursors,
        "de_props": de_props,
        "de_code": de_code,
        "de_methods": _methods(de_code),
        "printer": printer,
        "printer_device": printer.get("DEVICE") or (printer.get("DEVNAMES", {}).get("device")) or None,
        "orientation": {"1": "portrait", "2": "landscape"}.get(orient),
        "records": recs,
    }


parse_lb2 = parse_fr2  # labels share the FRX record layout


# --------------------------------------------------------------------------
# .dc2 (database container) and .db2 (free table structure)
# --------------------------------------------------------------------------

def _tag(block, name, default=""):
    # strict: require the closing tag. An open-ended fallback would swallow the
    # remainder of a 1.4 MB file on any tag it failed to close.
    m = re.search(rf"<{name}>(.*?)</{name}>", block, re.S)
    return m.group(1).strip() if m else default


def _cdata_tag(block, name, default=""):
    m = re.search(rf"<{name}>\s*<!\[CDATA\[(.*?)\]\]>\s*</{name}>", block, re.S)
    return m.group(1).strip() if m else default


def _blocks(text, tag):
    return re.findall(rf"<{tag}>(.*?)</{tag}>", text, re.S)


def parse_dc2(path):
    text = read(path)
    # VIEWS also contain <FIELDS>/<FIELD>; scope table parsing to the TABLES section
    tables_section = _tag(text, "TABLES") or ""
    views_section = _tag(text, "VIEWS") or ""

    tables = []
    for tb in _blocks(tables_section, "TABLE"):
        fields = []
        for fb in _blocks(tb, "FIELD"):
            fields.append({
                "name": _tag(fb, "Name"),
                "caption": _tag(fb, "Caption"),
                "default": _tag(fb, "DefaultValue"),
                "rule": _tag(fb, "RuleExpression"),
                "rule_text": _tag(fb, "RuleText"),
                "input_mask": _tag(fb, "InputMask"),
                "comment": _tag(fb, "Comment"),
            })
        # The DBC records only the tag name + uniqueness; the index KEY EXPRESSION
        # lives in the .cdx compound index file, which is binary and not dumped here.
        indexes = [{"name": _tag(ib, "Name"), "unique": _tag(ib, "IsUnique") == ".T.",
                    "comment": _tag(ib, "Comment")}
                   for ib in _blocks(tb, "INDEX")]
        field_order = [x.strip() for x in _tag(tb, "FIELD_ORDER").splitlines() if x.strip()]
        tables.append({
            "name": _tag(tb, "Name"),
            "path": _tag(tb, "Path"),
            "comment": _tag(tb, "Comment"),
            "insert_trigger": _tag(tb, "InsertTrigger"),
            "update_trigger": _tag(tb, "UpdateTrigger"),
            "delete_trigger": _tag(tb, "DeleteTrigger"),
            "rule": _tag(tb, "RuleExpression"),
            "rule_text": _tag(tb, "RuleText"),
            "primary_key": _tag(tb, "PrimaryKey"),
            "field_order": field_order,
            "field_count": len(fields),
            "fields": fields,
            "indexes": indexes,
        })

    views = []
    for vb in _blocks(views_section, "VIEW"):
        sql = _tag(vb, "SQL")
        # <Tables> is 'database!table' possibly comma-separated
        base = [t.strip().split("!")[-1].lower()
                for t in _tag(vb, "Tables").split(",") if t.strip()]
        views.append({
            "name": _tag(vb, "Name"),
            "comment": _tag(vb, "Comment"),
            "sql": sql,
            "field_count": len(_blocks(vb, "FIELD")),
            "base_tables": base,
            "parameters": _tag(vb, "ParameterList"),
            "updatable": _tag(vb, "SendUpdates") == ".T.",
            "source_type": "remote" if _tag(vb, "SourceType") == "2" else "local",
        })

    relations = [{"child": _tag(rb, "ChildTable"), "parent": _tag(rb, "ParentTable"),
                  "child_tag": _tag(rb, "ChildTag"), "parent_tag": _tag(rb, "ParentTag"),
                  "ri_insert": _tag(rb, "RIInsert"), "ri_update": _tag(rb, "RIUpdate"),
                  "ri_delete": _tag(rb, "RIDelete")}
                 for rb in _blocks(text, "RELATION")]

    procs = _cdata_tag(text, "STOREDPROCEDURES")

    trig = [t for t in tables if t["insert_trigger"] or t["update_trigger"] or t["delete_trigger"]]
    ruled = [t for t in tables if t["rule"]]
    field_rules = sum(1 for t in tables for f in t["fields"] if f["rule"])

    return {
        "file": os.path.basename(path), "path": path,
        "name": _tag(text, "Name"),
        "table_count": len(tables),
        "view_count": len(views),
        "tables": tables,
        "views": views,
        "relations": relations,
        "stored_procedures": procs,
        "stored_proc_lines": len(procs.splitlines()) if procs else 0,
        # Integrity summary: this DBC declares no RI, no triggers, no rules.
        "integrity": {
            "tables_with_triggers": len(trig),
            "tables_with_rules": len(ruled),
            "field_level_rules": field_rules,
            "relations": len(relations),
            "tables_with_primary_key": sum(1 for t in tables if t["primary_key"]),
            "index_count": sum(len(t["indexes"]) for t in tables),
        },
    }


def parse_db2(path):
    text = read(path)
    fields = [{"name": _tag(fb, "Name"), "type": _tag(fb, "Type"),
               "width": _tag(fb, "Width"), "decimals": _tag(fb, "Decimals"),
               "null": _tag(fb, "Null"), "rule": _tag(fb, "Field_Valid_Exp"),
               "rule_text": _tag(fb, "Field_Valid_Text"),
               "default": _tag(fb, "Field_Default_Value")}
              for fb in _blocks(text, "FIELD")]
    # a free table's structural CDX: <INDEX> blocks with TagName/TagType/Key/Filter/Order
    indexes = [{"name": _tag(ib, "TagName"), "kind": _tag(ib, "TagType").lower(),
                "key": _tag(ib, "Key"), "filter": _tag(ib, "Filter"),
                "order": _tag(ib, "Order").lower()}
               for ib in _blocks(text, "INDEX")]
    # table-level entries FoxBin2PRG writes on every FIELD block; read them once
    first = next(iter(_blocks(text, "FIELD")), "")
    return {
        "file": os.path.basename(path), "path": path,
        "table": os.path.splitext(os.path.basename(path))[0],
        "database": _tag(text, "Database"),
        "code_page": _tag(text, "CodePage"),
        "file_type": _tag(text, "FileType_Descrip"),
        "table_rule": _tag(first, "Table_Valid_Exp"),
        "insert_trigger": _tag(first, "Ins_Trig_Exp"),
        "update_trigger": _tag(first, "Upd_Trig_Exp"),
        "delete_trigger": _tag(first, "Del_Trig_Exp"),
        "field_count": len(fields), "fields": fields,
        "index_count": len(indexes), "indexes": indexes,
    }


# --------------------------------------------------------------------------
# .mn2 (menus)
# --------------------------------------------------------------------------
# FoxBin2PRG renders a menu as generated menu code inside marker comments:
#   *<MenuType>1</MenuType> *<MenuLocation>REPLACE|AFTER _MEDIT|...</MenuLocation>
#   *<SetupCode>..*</SetupCode>  *<MenuCode>..*</MenuCode>
#   *<Procedures>..*</Procedures>  *<CleanupCode>..*</CleanupCode>
# Menu code is DEFINE PAD / ON PAD .. ACTIVATE POPUP / DEFINE POPUP /
# DEFINE BAR / ON SELECTION BAR|POPUP|MENU / ON BAR .. ACTIVATE POPUP, with
# continuation lines ending in ';'. Bar-level procedures are named
# BAR_<n>_OF_<popup>_FB2P (the 2001 GENMENU .mpr names them _07y0s8...).
# Every separator bar ("\-") gets an ON BAR .. ACTIVATE POPUP to an empty
# generated popup: a twin artifact absent from the .mpr.

_MN_SECTION = re.compile(r"\*<(\w+)>(.*?)\*</\1>", re.S)
_MN_TAG = re.compile(r"\*<(MenuType|MenuLocation)>(.*?)</\1>")


def _join_continuations(code):
    out, buf = [], ""
    for line in code.splitlines():
        s = line.rstrip()
        if s.rstrip().endswith(";"):
            buf += s.rstrip()[:-1] + " "
        else:
            out.append((buf + s).strip()); buf = ""
    if buf:
        out.append(buf.strip())
    return [l for l in out if l]


def _mn_clause(stmt, key):
    """Value of a clause such as PROMPT "..", KEY .., MESSAGE "..", SKIP FOR .."""
    m = re.search(r"\b%s\s+(.*?)(?=\s+(?:PROMPT|KEY|MESSAGE|SKIP FOR|COLOR SCHEME|AFTER|BEFORE|MARGIN|SHADOW)\b|\s*&&|$)" % key, stmt, re.I)
    if not m:
        return ""
    v = m.group(1).strip()
    return v[1:-1] if len(v) >= 2 and v[0] == '"' and v[-1] == '"' else v


def parse_mn2(path):
    text = read(path)
    tags = dict(_MN_TAG.findall(text))
    sections = {k: v.strip("\r\n") for k, v in _MN_SECTION.findall(text)}
    code = sections.get("MenuCode", "")
    stmts = _join_continuations(code)

    pads, popups = [], {}
    for s in stmts:
        m = re.match(r'DEFINE PAD\s+"?([\w]+)"?\s+OF\s+(\w+)\s+(.*)', s, re.I)
        if m:
            rest = m.group(3)
            cm = re.search(r"&&\s*(.*)$", rest)
            pads.append({"name": m.group(1), "menu": m.group(2), "prompt": _mn_clause(rest, "PROMPT"),
                         "key": _mn_clause(rest, "KEY"), "message": _mn_clause(rest, "MESSAGE"),
                         "skip_for": _mn_clause(rest, "SKIP FOR"), "popup": "", "comment": cm.group(1).strip() if cm else "",
                         "bars": []})
            continue
        m = re.match(r"ON PAD\s+(\w+)\s+OF\s+(\w+)\s+ACTIVATE POPUP\s+(\w+)", s, re.I)
        if m:
            for p in pads:
                if p["name"].lower() == m.group(1).lower():
                    p["popup"] = m.group(3)
            continue
        m = re.match(r"DEFINE POPUP\s+(\w+)", s, re.I)
        if m:
            popups.setdefault(m.group(1).lower(), {"name": m.group(1), "bars": [], "on_selection": ""})
            continue
        m = re.match(r"DEFINE BAR\s+(\w+)\s+OF\s+(\w+)\s+(.*)", s, re.I)
        if m:
            rest = m.group(3)
            popups.setdefault(m.group(2).lower(), {"name": m.group(2), "bars": [], "on_selection": ""})["bars"].append(
                {"id": m.group(1), "prompt": _mn_clause(rest, "PROMPT"), "key": _mn_clause(rest, "KEY"),
                 "message": _mn_clause(rest, "MESSAGE"), "skip_for": _mn_clause(rest, "SKIP FOR"),
                 "action": "", "submenu": "", "separator": _mn_clause(rest, "PROMPT") == "\\-",
                 "system": m.group(1).startswith("_")})
            continue
        m = re.match(r"ON SELECTION BAR\s+(\w+)\s+OF\s+(\w+)\s+(.*)", s, re.I)
        if m:
            for b in popups.get(m.group(2).lower(), {"bars": []})["bars"]:
                if b["id"].lower() == m.group(1).lower():
                    b["action"] = m.group(3).strip()
            continue
        m = re.match(r"ON BAR\s+(\w+)\s+OF\s+(\w+)\s+ACTIVATE POPUP\s+(\w+)", s, re.I)
        if m:
            for b in popups.get(m.group(2).lower(), {"bars": []})["bars"]:
                if b["id"].lower() == m.group(1).lower():
                    b["submenu"] = m.group(3)
            continue
        m = re.match(r"ON SELECTION POPUP\s+(\w+)\s+(.*)", s, re.I)
        if m:
            popups.setdefault(m.group(1).lower(), {"name": m.group(1), "bars": [], "on_selection": ""})["on_selection"] = m.group(2).strip()
            continue
    for p in pads:
        if p["popup"]:
            p["bars"] = popups.get(p["popup"].lower(), {"bars": []})["bars"]
            p["popup_on_selection"] = popups.get(p["popup"].lower(), {}).get("on_selection", "")
    on_menu = next((s for s in stmts if re.match(r"ON SELECTION MENU\b", s, re.I)), "")

    procs = {}
    for m in re.finditer(r"^\s*PROCEDURE\s+(\w+)\s*$(.*?)^\s*ENDPROC", sections.get("Procedures", ""), re.S | re.M | re.I):
        procs[m.group(1)] = m.group(2).strip("\r\n")

    return {
        "file": os.path.basename(path), "path": path,
        "menu_type": tags.get("MenuType", ""), "location": tags.get("MenuLocation", ""),
        "setup_code": sections.get("SetupCode", ""), "cleanup_code": sections.get("CleanupCode", ""),
        "on_selection_menu": on_menu,
        "pad_count": len(pads), "bar_count": sum(len(p["bars"]) for p in popups.values()),
        "pads": pads, "popups": list(popups.values()), "procedures": procs,
        "empty_popups": sorted(p["name"] for p in popups.values() if not p["bars"]),
    }

# --------------------------------------------------------------------------
# .pj2 (project)
# --------------------------------------------------------------------------
# FoxBin2PRG renders a project as a program that rebuilds the .pjx:
# *<DevInfo> _Author = ".." *</DevInfo>, *<BuildProj> with .ADD('path') per
# member and a *< FileMetadata: Type=".." Cpid=".." ObjRev=".." /> comment,
# *<FileComments> (.Description), *<ExcludedFiles> (.Exclude = .T.),
# *<TextFiles> (.Type = 'T'), *<ProjectProperties> (.SetMain, .Debug,
# .Encrypted, .ProjectHookClass), and *<.HomeDir = '..' />.
# PJX type codes as written by VFP (case matters): lowercase d is the
# database container, uppercase D a table, x an "other" file (icons,
# bitmaps, masks). Contained tables are not listed; free tables are.

_PJ_ADD = re.compile(r"\.ADD\('([^']+)'\)\s*(?:&&\s*\*<\s*FileMetadata:\s*([^/]*)/>)?")
_PJ_META = re.compile(r'(\w+)="([^"]*)"')
PJ_TYPE = {"P": "program", "K": "form", "R": "report", "B": "label",
           "M": "menu", "V": "class library", "d": "database", "D": "table",
           "Q": "query", "T": "text", "L": "API library", "x": "other",
           "Z": "application", "H": "help"}


def parse_pj2(path):
    text = read(path)
    files = []
    for m in _PJ_ADD.finditer(text):
        p = m.group(1)
        meta = dict(_PJ_META.findall(m.group(2) or ""))
        code = meta.get("Type", "")
        files.append({"path": p, "type_code": code,
                      "type": PJ_TYPE.get(code, "unknown"),
                      "ext": os.path.splitext(p)[1].lower(),
                      "cpid": meta.get("Cpid", ""), "objrev": meta.get("ObjRev", ""),
                      "description": "", "excluded": False, "text_override": False})
    by_path = {f["path"].lower(): f for f in files}

    def _item(rx):
        for m in re.finditer(rx, text):
            f = by_path.get(m.group(1).lower())
            if f:
                yield f, m
    for f, m in _item(r"\.ITEM\(lcCurdir \+ '([^']+)'\)\.Description = '((?:[^']|'')*)'"):
        f["description"] = m.group(2).replace("''", "'")
    for f, m in _item(r"\.ITEM\(lcCurdir \+ '([^']+)'\)\.Exclude = \.T\."):
        f["excluded"] = True
    for f, m in _item(r"\.ITEM\(lcCurdir \+ '([^']+)'\)\.Type = 'T'"):
        f["text_override"] = True

    dev = {k: v for k, v in re.findall(r"^_(\w+)\s*=\s*\"([^\"]*)\"", text, re.M)}
    meta = {k: dev.get(k, "") for k in ("ProductName", "CompanyName", "MajorVer", "MinorVer",
                                        "Revision", "LegalCopyright", "Comments")}
    props = {}
    for k, v in re.findall(r"^\s*\.(\w+)\s*=\s*(.+?)\s*$", text.split("*<ProjectProperties>", 1)[-1].split("*</ProjectProperties>", 1)[0], re.M):
        props[k] = v
    for k, v in re.findall(r"\*<\.(\w+)\s*=\s*(.+?)\s*/>", text):
        props.setdefault(k, v)
    main = re.search(r"\.SetMain\(lcCurdir \+ '([^']+)'\)", text)
    home = re.search(r"\*<\.HomeDir\s*=\s*'([^']*)'", text)
    return {"file": os.path.basename(path), "path": path, "meta": meta, "dev_info": dev,
            "home_dir": home.group(1) if home else None,
            "main_file": main.group(1) if main else None,
            "properties": props,
            "file_count": len(files), "files": files,
            "excluded": [f["path"] for f in files if f["excluded"]],
            "type_counts": {t: sum(1 for f in files if f["type"] == t) for t in sorted({f["type"] for f in files})}}

# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------

PARSERS = {".sc2": parse_sc2, ".vc2": parse_vc2, ".fr2": parse_fr2,
           ".lb2": parse_fr2, ".dc2": parse_dc2, ".db2": parse_db2,
           ".pj2": parse_pj2, ".mn2": parse_mn2}


def parse_any(path):
    """Dispatch on extension. Raises ValueError for a non-twin file."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in PARSERS:
        raise ValueError("not a FoxBin2PRG twin: " + path)
    return PARSERS[ext](path)


def iter_twins(root):
    """Yield every twin file under root, sorted, any depth."""
    for dirpath, _dirs, files in os.walk(root):
        for fn in sorted(files):
            if os.path.splitext(fn)[1].lower() in PARSERS:
                yield os.path.join(dirpath, fn)


def summary_line(result, rel):
    """One line per artifact: counts for list/dict fields, values for scalars."""
    parts = []
    for k, v in result.items():
        if k in ("file", "path"):
            continue
        if isinstance(v, (list, dict)):
            parts.append("%s=%d" % (k, len(v)))
        elif isinstance(v, str):
            if v and "\n" not in v and len(v) <= 40:
                parts.append("%s=%s" % (k, v))
        elif v is not None:
            parts.append("%s=%s" % (k, v))
    return rel + ": " + " ".join(parts)


def _main(argv=None):
    import argparse, json, sys
    ap = argparse.ArgumentParser(
        description="Parse FoxBin2PRG text twins (.sc2 .vc2 .fr2 .lb2 .dc2 .db2 .pj2 .mn2) "
                    "to JSON, or print a one-line summary per artifact.")
    ap.add_argument("paths", nargs="+", help="twin files and/or directories to walk")
    ap.add_argument("--summary", action="store_true",
                    help="one line per artifact instead of full JSON")
    ap.add_argument("--json", metavar="OUT", help="write full JSON to this file")
    args = ap.parse_args(argv)

    targets = []
    for p in args.paths:
        if os.path.isdir(p):
            targets.extend(iter_twins(p))
        else:
            targets.append(p)
    if not targets:
        print("no twins found", file=sys.stderr)
        return 1
    abs_targets = [os.path.abspath(t) for t in targets]
    root = os.path.commonpath(abs_targets) if len(abs_targets) > 1 else os.path.dirname(abs_targets[0])
    if os.path.isfile(root):
        root = os.path.dirname(root)

    results, failures = [], []
    for t in abs_targets:
        rel = os.path.relpath(t, root).replace("\\", "/")
        try:
            r = parse_any(t)
        except Exception as e:  # keep going; report at the end
            failures.append((rel, "%s: %s" % (type(e).__name__, e)))
            continue
        results.append(r)
        if args.summary:
            print(summary_line(r, rel))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1, default=str)
    elif not args.summary:
        json.dump(results if len(results) > 1 else (results[0] if results else {}),
                  sys.stdout, indent=1, default=str)
        print()

    for rel, err in failures:
        print("FAIL %s: %s" % (rel, err), file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
