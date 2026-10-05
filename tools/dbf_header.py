"""
Read Visual FoxPro / dBase table metadata WITHOUT touching row data.

Only the 32-byte file header plus the 32-byte-per-field descriptor array are read.
Record data pages are never opened, so a 1.7 GB table costs the same as a 2 KB one.

Usage:
    python dbf_header.py <dir> [--json out.json]
"""
import argparse
import json
import os
import struct
import sys

# DBF version byte -> human label. VFP writes 0x30/0x31/0x32.
VERSIONS = {
    0x02: "FoxBASE",
    0x03: "dBase III+ / FoxBASE+ (no memo)",
    0x30: "Visual FoxPro",
    0x31: "Visual FoxPro (autoincrement)",
    0x32: "Visual FoxPro (varchar/varbinary)",
    0x43: "dBase IV SQL table",
    0x83: "dBase III+ with memo",
    0xF5: "FoxPro 2.x with memo",
    0xFB: "FoxPro (no memo)",
}

TYPE_NAMES = {
    "C": "Character", "N": "Numeric", "F": "Float", "I": "Integer",
    "B": "Double", "Y": "Currency", "D": "Date", "T": "DateTime",
    "L": "Logical", "M": "Memo", "G": "General", "P": "Picture",
    "Q": "Varbinary", "V": "Varchar", "W": "Blob", "0": "_NullFlags",
}

# Field descriptor flag bits (VFP)
FLAG_SYSTEM = 0x01
FLAG_NULLABLE = 0x02
FLAG_BINARY = 0x04
FLAG_AUTOINC = 0x0C


def read_header(path):
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(32)
        if len(head) < 32:
            raise ValueError("file shorter than a DBF header")

        version = head[0]
        yy, mm, dd = head[1], head[2], head[3]
        (records,) = struct.unpack("<I", head[4:8])
        (header_len,) = struct.unpack("<H", head[8:10])
        (record_len,) = struct.unpack("<H", head[10:12])
        flags = head[28]
        code_page = head[29]

        # Field descriptors run from offset 32 until a 0x0D terminator.
        fields = []
        f.seek(32)
        while True:
            desc = f.read(32)
            if len(desc) < 32 or desc[0] == 0x0D:
                break
            name = desc[0:11].split(b"\x00")[0].decode("latin-1", "replace")
            ftype = chr(desc[11])
            flen = desc[16]
            fdec = desc[17]
            fflags = desc[18]
            fields.append({
                "name": name,
                "type": ftype,
                "type_name": TYPE_NAMES.get(ftype, ftype),
                "width": flen,
                "decimals": fdec,
                "nullable": bool(fflags & FLAG_NULLABLE),
                "binary": bool(fflags & FLAG_BINARY),
                "system": bool(fflags & FLAG_SYSTEM),
                "autoinc": (fflags & FLAG_AUTOINC) == FLAG_AUTOINC,
            })

    year = 1900 + yy if yy >= 80 else 2000 + yy

    # Sanity: does the physical size agree with header math? A mismatch means a
    # truncated / corrupt / still-being-written table, which is worth surfacing
    # rather than silently reporting a bogus row count.
    expected = header_len + records * record_len
    consistent = abs(size - expected) <= record_len + 1

    return {
        "file": os.path.basename(path),
        "path": path,
        "bytes": size,
        "mb": round(size / (1024 * 1024), 2),
        "version_byte": f"0x{version:02X}",
        "version": VERSIONS.get(version, f"unknown (0x{version:02X})"),
        "last_update": f"{year:04d}-{mm:02d}-{dd:02d}" if mm else None,
        "records": records,
        "header_len": header_len,
        "record_len": record_len,
        "has_memo": bool(flags & 0x02) or version in (0x30, 0x31, 0x32, 0x83, 0xF5),
        "has_dbc_backlink": bool(flags & 0x01),
        "code_page": code_page,
        "field_count": len(fields),
        "fields": fields,
        "size_consistent": consistent,
        "expected_bytes": expected,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("directory")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--recurse", action="store_true")
    args = ap.parse_args()

    names = []
    if args.recurse:
        for r, _d, fs in os.walk(args.directory):
            names += [os.path.join(r, x) for x in fs if x.lower().endswith(".dbf")]
    else:
        names = [os.path.join(args.directory, x)
                 for x in os.listdir(args.directory) if x.lower().endswith(".dbf")]

    out, errors = [], []
    for p in sorted(names, key=str.lower):
        try:
            out.append(read_header(p))
        except Exception as e:  # keep going; one bad table shouldn't abort the sweep
            errors.append({"path": p, "error": str(e)})

    out.sort(key=lambda r: -r["bytes"])

    print(f"tables: {len(out)}   errors: {len(errors)}")
    print(f"total rows: {sum(r['records'] for r in out):,}")
    print(f"total size: {sum(r['bytes'] for r in out) / 1024**3:.2f} GB")
    bad = [r for r in out if not r["size_consistent"]]
    if bad:
        print(f"\nWARNING: {len(bad)} table(s) whose size disagrees with header math:")
        for r in bad[:10]:
            print(f"  {r['file']:<24} actual={r['bytes']:>12,}  expected={r['expected_bytes']:>12,}")
    if errors:
        print("\nerrors:")
        for e in errors:
            print(f"  {e['path']}: {e['error']}")

    print(f"\n{'table':<26}{'rows':>12}{'MB':>10}{'flds':>6}")
    for r in out[:20]:
        print(f"{r['file']:<26}{r['records']:>12,}{r['mb']:>10.1f}{r['field_count']:>6}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"tables": out, "errors": errors}, f, indent=1)
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    sys.exit(main())
