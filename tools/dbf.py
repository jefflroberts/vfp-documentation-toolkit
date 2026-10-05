"""Self-contained VFP DBF + FPT memo reader (no external deps).
Supports field types C, N, F, I, B, Y, L, D, T, M. Returns active (non-deleted) rows
as dicts with lowercased field names. Memo (M) fields resolved from the sibling .fpt."""
import struct, os, datetime

def _read_fpt(fpt_path):
    if not os.path.exists(fpt_path):
        return None, 64
    with open(fpt_path, 'rb') as f:
        data = f.read()
    block_size = struct.unpack('>H', data[6:8])[0] or 64
    return data, block_size

def read_table(dbf_path, memo_path=None):
    if memo_path is None:
        base = os.path.splitext(dbf_path)[0]
        # VFP tables use .fpt; VFP reports (.frx/.lbx) use .frt/.lbt for their memos
        for ext in ('.fpt', '.frt', '.lbt'):
            if os.path.exists(base + ext):
                memo_path = base + ext
                break
        else:
            memo_path = base + '.fpt'
    fpt, bs = _read_fpt(memo_path)
    with open(dbf_path, 'rb') as f:
        data = f.read()
    nrec = struct.unpack('<I', data[4:8])[0]
    hlen = struct.unpack('<H', data[8:10])[0]
    rlen = struct.unpack('<H', data[10:12])[0]
    # field descriptors
    fields = []
    pos = 32
    while data[pos] != 0x0d:
        fd = data[pos:pos+32]
        name = fd[0:11].split(b'\x00')[0].decode('ascii', 'replace').lower()
        ftype = chr(fd[11])
        flen = fd[16]
        dec = fd[17]
        fields.append((name, ftype, flen, dec))
        pos += 32

    def memo(raw):
        raw = raw.strip()
        if not raw or fpt is None:
            return ''
        try:
            blk = int(raw)
        except ValueError:
            blk = struct.unpack('<I', raw.ljust(4, b'\x00')[:4])[0]
        if blk == 0:
            return ''
        off = blk * bs
        mlen = struct.unpack('>I', fpt[off+4:off+8])[0]
        return fpt[off+8:off+8+mlen].decode('latin-1', 'replace')

    rows = []
    o = hlen
    for _ in range(nrec):
        rec = data[o:o+rlen]; o += rlen
        if not rec or rec[0:1] == b'*':
            continue
        d = {}
        p = 1
        for name, ftype, flen, dec in fields:
            raw = rec[p:p+flen]; p += flen
            if ftype in 'C':
                d[name] = raw.decode('latin-1', 'replace').rstrip()
            elif ftype in 'NF':
                s = raw.strip()
                try:
                    d[name] = (float(s) if (b'.' in s or dec) else int(s)) if s else None
                except ValueError:
                    # VFP fills a numeric field with '*****' when the stored value
                    # overflows the column width. Treat it as unknown, not fatal.
                    d[name] = None
            elif ftype == 'I':
                d[name] = struct.unpack('<i', raw[:4])[0] if len(raw) >= 4 else None
            elif ftype == 'B':
                d[name] = struct.unpack('<d', raw[:8])[0] if len(raw) >= 8 else None
            elif ftype == 'Y':
                d[name] = struct.unpack('<q', raw[:8])[0] / 10000.0 if len(raw) >= 8 else None
            elif ftype == 'L':
                d[name] = raw[:1] in (b'T', b't', b'Y', b'y')
            elif ftype == 'D':
                s = raw.strip().decode('ascii', 'replace')
                d[name] = s if len(s) == 8 and s.isdigit() else None
            elif ftype == 'T':
                if len(raw) >= 8:
                    jd, ms = struct.unpack('<ii', raw[:8])
                    d[name] = jd
                else:
                    d[name] = None
            elif ftype == 'M':
                d[name] = memo(raw)
            else:
                d[name] = raw
        rows.append(d)
    return fields, rows

if __name__ == '__main__':
    import sys
    fields, rows = read_table(sys.argv[1])
    print("fields:", [(f[0], f[1]) for f in fields])
    print("active rows:", len(rows))
    if rows:
        print("sample:", {k: rows[0][k] for k in list(rows[0])[:8]})
