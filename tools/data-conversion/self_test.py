#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
self_test.py
============
Pre-flight check for the portable appdata converter. Run this FIRST on any new
machine (especially an old Windows XP / Windows 7 box) to confirm the bundle is
wired up correctly BEFORE trying a real conversion.

It checks, in order:
  1. Python version + bitness are suitable (and XP-compatible if on XP).
  2. The bundled (vendored) ./dbfread imports -- and is the local copy, not a
     pip-installed one.
  3. sqlite3 works end-to-end (create table, insert, read back).
  4. If a data folder is given/found: appdata.dbc parses and a real .dbf reads.

Usage:
    python self_test.py                      (environment checks only)
    python self_test.py --data "C:\\vfp\\data"  (also tests reading real data)
    self_test.bat "C:\\vfp\\data"             (same, via the bundled Python)

Exit code is 0 if everything required passed, 1 otherwise.
3.4-compatible (no f-strings), like the converter itself.
"""
import os
import platform
import struct
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

_failures = []
_warnings = []


def ok(msg):
    print("  [ OK ]  " + msg)


def warn(msg):
    print("  [WARN]  " + msg)
    _warnings.append(msg)


def fail(msg):
    print("  [FAIL]  " + msg)
    _failures.append(msg)


def check_python():
    print("1. Python interpreter")
    vi = sys.version_info
    bits = struct.calcsize("P") * 8
    print("       version : %d.%d.%d (%d-bit)" % (vi[0], vi[1], vi[2], bits))
    print("       exe     : %s" % sys.executable)
    print("       windows : %s" % platform.platform())

    if vi[0] != 3:
        fail("Python 3 is required (found Python %d)." % vi[0])
        return
    if vi[1] < 4:
        fail("Python 3.4+ is required (found 3.%d)." % vi[1])
    else:
        ok("Python 3.%d is supported by this tool." % vi[1])

    # Windows-edition specific guidance.
    rel = platform.release()  # '7', 'XP', '8', '10', '2003Server', etc.
    if rel in ("XP", "2003Server", "2003"):
        if (vi[0], vi[1]) != (3, 4):
            fail("On Windows XP you MUST use Python 3.4.4 (3.5+ won't run on XP).")
        else:
            ok("Python 3.4 on Windows XP -- correct combination.")
        if bits != 32:
            warn("64-bit Python on XP is unusual; the 32-bit 3.4.4 build is the "
                 "safe choice.")
    elif rel == "7":
        if vi[1] > 8:
            fail("On Windows 7 use Python 3.4-3.8 (3.9+ won't run on Win 7).")
        else:
            ok("Python 3.%d on Windows 7 -- supported." % vi[1])


def check_dbfread():
    print("2. Bundled dbfread")
    try:
        import dbfread
    except Exception as e:
        fail("could not import dbfread: %s" % e)
        return None
    ver = getattr(dbfread, "__version__", "?")
    where = os.path.dirname(os.path.abspath(dbfread.__file__))
    print("       version : %s" % ver)
    print("       path    : %s" % where)
    if os.path.normcase(where).startswith(os.path.normcase(_SCRIPT_DIR)):
        ok("Using the BUNDLED dbfread next to this script (no pip needed).")
    else:
        warn("dbfread is being imported from OUTSIDE this folder (%s). The "
             "bundled copy should win; check there's no other dbfread on the "
             "machine." % where)
    return dbfread


def check_sqlite():
    print("3. sqlite3 (bundled in Python)")
    try:
        import sqlite3
    except Exception as e:
        fail("could not import sqlite3: %s" % e)
        return
    # sqlite3.version (the pysqlite wrapper version) was removed in Python 3.12;
    # it still exists on 3.4. Guard it so this test runs on every Python.
    modver = getattr(sqlite3, "version", "n/a")
    print("       sqlite  : %s (module %s)" % (sqlite3.sqlite_version, modver))
    try:
        con = sqlite3.connect(":memory:")
        cur = con.cursor()
        cur.execute('CREATE TABLE t ("a", "b")')
        cur.executemany('INSERT INTO t VALUES (?, ?)', [(1, "x"), (2, "y")])
        con.commit()
        rows = cur.execute("SELECT count(*) FROM t").fetchone()[0]
        con.close()
        if rows == 2:
            ok("sqlite3 create/insert/read works.")
        else:
            fail("sqlite3 round-trip returned %r rows, expected 2." % rows)
    except Exception as e:
        fail("sqlite3 round-trip failed: %s" % e)


def find_data_dir(arg_data):
    if arg_data:
        return arg_data
    cand = os.path.join(_SCRIPT_DIR, "data")
    if os.path.isdir(cand):
        return cand
    return None


def check_data(data_dir):
    print("4. Real data read (optional)")
    if not data_dir:
        warn("no --data folder given and no .\\data folder present -- skipping "
             "the live read test. Re-run with --data \"<vfp data folder>\" on "
             "the client machine to fully validate.")
        return
    if not os.path.isdir(data_dir):
        fail("--data folder not found: %s" % data_dir)
        return
    print("       folder  : %s" % data_dir)
    from dbfread import DBF

    # 4a. the .dbc (the long-field-name container), picked the way the
    # converter picks it
    from build_appdata_sqlite_portable import find_dbc
    dbc, candidates = find_dbc(data_dir)
    if dbc:
        name = os.path.basename(dbc)
        try:
            d = DBF(dbc, load=False, ignore_missing_memofile=True,
                    char_decode_errors="replace", lowernames=True)
            seen = 0
            for _ in d:
                seen += 1
                if seen >= 5:
                    break
            ok("%s opened and read (%d+ container rows)." % (name, seen))
        except Exception as e:
            fail("%s present but failed to read: %s" % (name, e))
    elif candidates:
        fail("several .dbc containers and none is appdata.dbc -- pass --dbc "
             "to the converter: %s" % ", ".join(os.path.basename(c) for c in candidates))
    else:
        warn("no .dbc in the data folder -- the converter will fall back "
             "to truncated physical field names.")

    # 4b. one real .dbf
    dbfs = [f for f in os.listdir(data_dir) if f.lower().endswith(".dbf")
            and not f.lower().endswith(".dbc")]
    if not dbfs:
        fail("no .dbf files found in %s" % data_dir)
        return
    sample = sorted(dbfs)[0]
    try:
        t = DBF(os.path.join(data_dir, sample), load=False,
                ignore_missing_memofile=True, char_decode_errors="replace",
                lowernames=True)
        ncols = len(t.field_names)
        seen = 0
        for _ in t:
            seen += 1
            if seen >= 3:
                break
        ok("read sample table %s (%d cols, %d+ rows)." % (sample, ncols, seen))
    except Exception as e:
        fail("failed to read sample table %s: %s" % (sample, e))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    data_dir = None
    if "--data" in argv:
        i = argv.index("--data")
        if i + 1 < len(argv):
            data_dir = argv[i + 1]

    print("=" * 60)
    print(" Portable VFP->SQLite converter -- self test")
    print("=" * 60)
    check_python()
    print("")
    dbfread = check_dbfread()
    print("")
    check_sqlite()
    print("")
    check_data(find_data_dir(data_dir) if dbfread is not None else None)
    print("")
    print("=" * 60)
    if _failures:
        print(" RESULT: FAIL  (%d problem(s))" % len(_failures))
        for m in _failures:
            print("   - " + m)
        if _warnings:
            print(" warnings:")
            for m in _warnings:
                print("   - " + m)
        return 1
    if _warnings:
        print(" RESULT: PASS (with %d warning(s) -- review above)"
              % len(_warnings))
    else:
        print(" RESULT: PASS -- bundle is ready to use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
