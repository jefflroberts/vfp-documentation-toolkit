#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_appdata_sqlite_portable.py
================================
PORTABLE clone of a Visual FoxPro `appdata.dbc` database (a folder of
.dbf/.fpt/.cdx files) into a single queryable SQLite database.

This is a field-portable version of a modern-Python converter, intended to run
on the CLIENT'S OLD MACHINES (Windows XP / Windows 7) during the early parity
phase of the rebuild, where it produces appdata.sqlite directly.

Differences from the original (BEHAVIOUR IS IDENTICAL — verified row-for-row):
  * No f-strings: written in Python 3.4-compatible syntax. The one CPython that
    runs on BOTH Windows XP and Windows 7 is 3.4.4; 3.5+ drops XP, 3.9+ drops 7.
    This file also runs unchanged on any later Python 3.x (tested on 3.14).
  * `dbfread` is VENDORED in a sibling ./dbfread folder, so NO pip / internet is
    required on the old machine (pip against modern PyPI fails on XP due to TLS).
    sqlite3 ships inside CPython itself, so the .sqlite is written on-site.
  * Default paths are derived from this script's own location (drop a `data`
    folder next to it, or pass --data), instead of hard-coded paths.

Why the .dbc parsing exists
---------------------------
VFP .dbf files store only the *physical* field names, truncated to 10 chars
(and collision-disambiguated, e.g. `nlouvercountbottom` -> `nlouverco2`). The
full names live in the database container (.dbc). This script reads the .dbc,
recovers the full field names, and uses them as the SQLite column names so the
parity spec's SQL runs as written.

It is re-runnable: point --data at a newer folder and it rebuilds from scratch.

Usage
-----
    python build_appdata_sqlite_portable.py --data "C:\\path\\to\\vfp\\data"

    # --out defaults to <script dir>\\appdata.sqlite
    # --dbc defaults to the only .dbc in <data> (appdata.dbc if there are several)
    # On the old machines, just use build.bat (see README.txt).

Requires: nothing to install — Python 3.4+ with the bundled ./dbfread folder.
"""
import argparse
import datetime
import glob
import os
import sqlite3
import sys
from collections import defaultdict

# Make sure the vendored ./dbfread (sibling of this file) is importable even if
# the script is launched from another working directory.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from dbfread import DBF

DEFAULT_DATA = os.path.join(_SCRIPT_DIR, "data")
DEFAULT_OUT = os.path.join(_SCRIPT_DIR, "appdata.sqlite")

# A physical .dbf is mapped to a .dbc table only when at least this fraction of
# its fields match positionally by name prefix. Prevents mis-mapping free tables
# that happen to share a field count with a container table.
MATCH_THRESHOLD = 0.6
PREFIX = 8  # compare first N chars (truncation keeps >=8 identical; only the
            # 9th/10th char changes under collision disambiguation)


def sanitize(v):
    """Coerce a dbfread value into something sqlite3 accepts."""
    if v is None:
        return None
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    if isinstance(v, bytes):
        try:
            return v.decode("latin1")
        except Exception:
            return repr(v)
    return v


def parse_dbc(dbc_path):
    """Return {table_name_lower: [full_field_names_in_order]} from the container."""
    dbc = DBF(dbc_path, load=True, ignore_missing_memofile=True,
              char_decode_errors="replace", lowernames=True)
    table_name = {}          # objectid -> table name
    fields = defaultdict(list)  # parentid -> [field names in row order]
    for r in dbc:
        ot = (r.get("objecttype") or "").strip()
        if ot == "Table":
            table_name[r["objectid"]] = (r.get("objectname") or "").strip()
        elif ot == "Field":
            fields[r.get("parentid")].append((r.get("objectname") or "").strip())
    return dict((table_name[oid], flds) for oid, flds in fields.items()
                if oid in table_name)


def best_dbc_match(physical_fields, dbc_tables):
    """Find the .dbc table whose full field list best matches these physical
    columns positionally. Returns (table_name, full_fields) or (None, None)."""
    best = (None, None, 0.0)
    n = len(physical_fields)
    if n == 0:
        return None, None
    for name, full in dbc_tables.items():
        if len(full) != n:
            continue
        hits = sum(
            1 for p, f in zip(physical_fields, full)
            if p.lower()[:PREFIX] == f.lower()[:PREFIX]
        )
        score = hits / n
        if score > best[2]:
            best = (name, full, score)
    if best[2] >= MATCH_THRESHOLD:
        return best[0], best[1]
    return None, None


def find_dbc(data_dir):
    """Pick the database container in data_dir. Returns (path, candidates):
    the only .dbc if there is one, appdata.dbc if there are several and one has
    that name, else (None, candidates) so the caller can ask for --dbc."""
    found = {}
    for p in glob.glob(os.path.join(data_dir, "*.dbc")) + \
             glob.glob(os.path.join(data_dir, "*.DBC")):
        found.setdefault(os.path.basename(p).lower(), p)
    candidates = [found[k] for k in sorted(found)]
    if len(candidates) == 1:
        return candidates[0], candidates
    if "appdata.dbc" in found:
        return found["appdata.dbc"], candidates
    return None, candidates


def build(data_dir, out_path, dbc_path):
    dbc_tables = parse_dbc(dbc_path) if dbc_path and os.path.exists(dbc_path) else {}
    if not dbc_tables:
        print("WARNING: no .dbc parsed {0}; using physical names only."
              .format("at " + dbc_path if dbc_path else "(none in the data folder)"))

    if os.path.exists(out_path):
        os.remove(out_path)
    con = sqlite3.connect(out_path)
    cur = con.cursor()

    # case-insensitive de-dup of .dbf files
    paths = {}
    for p in glob.glob(os.path.join(data_dir, "*.dbf")) + \
             glob.glob(os.path.join(data_dir, "*.DBF")):
        paths.setdefault(os.path.basename(p).lower(), p)

    report = []
    for low, path in sorted(paths.items()):
        tname = os.path.splitext(low)[0]
        try:
            t = DBF(path, load=False, ignore_missing_memofile=True,
                    char_decode_errors="replace", lowernames=True)
            physical = list(t.field_names)
            if not physical:
                report.append((tname, "SKIP", "no fields", ""))
                continue

            dbc_name, full = best_dbc_match(physical, dbc_tables)
            if full:
                cols = [f.lower() for f in full]
                src = "dbc:{0}".format(dbc_name)
                renamed = sum(1 for a, b in zip(physical, cols) if a != b)
            else:
                cols = physical
                src = "physical"
                renamed = 0

            coldef = ", ".join('"{0}"'.format(c) for c in cols)
            cur.execute('CREATE TABLE "{0}" ({1})'.format(tname, coldef))
            ins = 'INSERT INTO "{0}" VALUES ({1})'.format(
                tname, ", ".join("?" for _ in cols))

            n = 0
            batch = []
            for rec in t:
                batch.append([sanitize(rec.get(c)) for c in physical])
                n += 1
                if len(batch) >= 2000:
                    cur.executemany(ins, batch)
                    batch = []
            if batch:
                cur.executemany(ins, batch)
            con.commit()
            report.append((tname, "OK", "{0} rows / {1} cols".format(n, len(cols)),
                           "{0}, {1} renamed".format(src, renamed)))
        except Exception as e:
            report.append((tname, "ERROR", str(e).replace("\n", " ")[:90], ""))

    con.commit()
    con.close()

    print("\nSQLite written: {0}".format(out_path))
    print("DBC tables parsed: {0}\n".format(len(dbc_tables)))
    print("{0:30} {1:6} {2:22} source".format("table", "status", "detail"))
    print("-" * 92)
    for tn, st, dt, src in report:
        print("{0:30} {1:6} {2:22} {3}".format(tn, st, dt, src))
    unmapped = [r[0] for r in report if r[1] == "OK" and r[3].startswith("physical")]
    if unmapped:
        print("\nFree tables (no .dbc entry, physical names kept): "
              + ", ".join(unmapped))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=DEFAULT_DATA, help="folder of .dbf files")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output .sqlite path")
    ap.add_argument("--dbc", default=None,
                    help="path to the .dbc container (default: the only .dbc in "
                         "--data, or appdata.dbc if there are several)")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.data):
        sys.exit("--data dir not found: {0}".format(args.data))
    dbc = args.dbc
    if not dbc:
        dbc, candidates = find_dbc(args.data)
        if not dbc and candidates:
            sys.exit("Several .dbc containers in {0}; pick one with --dbc:\n  {1}"
                     .format(args.data, "\n  ".join(candidates)))
    if dbc:
        print("Using container: {0}".format(dbc))
    build(args.data, args.out, dbc)


if __name__ == "__main__":
    main()
