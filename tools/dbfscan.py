"""Minimal DBF reader: record counts + numeric/date field ranges (no memo needed).

CLI: scan one or more folders of .dbf tables and report total/active/deleted counts,
optionally with the min..max range of a chosen field.

    python dbfscan.py <data-dir> [<data-dir> ...] [--tables t1 t2] [--field ipkey]
"""
import struct, os, sys, glob, argparse

def read_dbf_meta(path):
    with open(path, 'rb') as f:
        hdr = f.read(32)
        nrec = struct.unpack('<I', hdr[4:8])[0]
        hlen = struct.unpack('<H', hdr[8:10])[0]
        rlen = struct.unpack('<H', hdr[10:12])[0]
        # field descriptors
        fields = []
        pos = 32
        f.seek(32)
        while True:
            fd = f.read(32)
            if fd[0:1] == b'\x0d' or len(fd) < 32:
                break
            name = fd[0:11].split(b'\x00')[0].decode('ascii', 'replace')
            ftype = chr(fd[11])
            flen = fd[16]
            fields.append((name, ftype, flen))
        return nrec, hlen, rlen, fields

def scan(path, want_fields=()):
    nrec, hlen, rlen, fields = read_dbf_meta(path)
    # compute offsets
    offs = {}
    o = 1
    for nm, ft, fl in fields:
        offs[nm.lower()] = (o, ft, fl)
        o += fl
    active = deleted = 0
    ranges = {wf: [None, None] for wf in want_fields}
    with open(path, 'rb') as f:
        f.seek(hlen)
        for _ in range(nrec):
            rec = f.read(rlen)
            if not rec or len(rec) < 1:
                break
            if rec[0:1] == b'*':
                deleted += 1
                continue
            active += 1
            for wf in want_fields:
                if wf in offs:
                    so, ft, fl = offs[wf]
                    raw = rec[so:so+fl].strip()
                    if not raw:
                        continue
                    try:
                        val = float(raw) if ft in 'NI' else raw.decode('ascii', 'replace')
                    except Exception:
                        continue
                    lo, hi = ranges[wf]
                    if isinstance(val, float):
                        ranges[wf][0] = val if lo is None else min(lo, val)
                        ranges[wf][1] = val if hi is None else max(hi, val)
    return nrec, active, deleted, ranges, [n for n, _, _ in fields]

def _dbf_paths(base, tables):
    """Resolve the .dbf files to scan in `base`: an explicit table list, or all .dbf
    (case-insensitively de-duped)."""
    if tables:
        return [(t, os.path.join(base, t + '.dbf')) for t in tables]
    seen = {}
    for p in glob.glob(os.path.join(base, '*.dbf')) + glob.glob(os.path.join(base, '*.DBF')):
        seen.setdefault(os.path.basename(p).lower(), p)
    return [(os.path.splitext(os.path.basename(seen[k]))[0], seen[k]) for k in sorted(seen)]

def _fmt_range(rng):
    lo, hi = rng
    lo = int(lo) if lo is not None else '?'
    hi = int(hi) if hi is not None else '?'
    return "{0}..{1}".format(lo, hi)

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Scan VFP .dbf tables: total/active/deleted counts + optional field range.")
    ap.add_argument('data_dirs', nargs='+', help='one or more folders containing .dbf files')
    ap.add_argument('--tables', nargs='*', default=None,
                    help='table names (without .dbf) to scan; default: every .dbf in each folder')
    ap.add_argument('--field', default=None,
                    help='numeric field to report a min..max range for (e.g. ipkey)')
    args = ap.parse_args(argv)

    want = (args.field,) if args.field else ()
    hdr_field = ("  " + args.field + " range") if args.field else ""
    for base in args.data_dirs:
        print("\n" + base)
        print("  {0:24}{1:>8}{2:>8}{3:>7}{4}".format('table', 'total', 'active', 'del', hdr_field))
        for tbl, p in _dbf_paths(base, args.tables):
            if not os.path.exists(p):
                print("  {0:24}  (absent)".format(tbl))
                continue
            nrec, active, deleted, ranges, _ = scan(p, want)
            extra = ("  " + _fmt_range(ranges[args.field])) if args.field else ""
            print("  {0:24}{1:>8}{2:>8}{3:>7}{4}".format(tbl, nrec, active, deleted, extra))

if __name__ == '__main__':
    main()
