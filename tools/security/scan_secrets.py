"""
Locate hardcoded credentials across a VFP source tree.

Reports FILE:LINE and the *kind* of secret only. Values are never printed and never
written to disk -- the point is to tell a maintainer where to look, not to mint another
copy of the secret in a documentation file. Use this to WRITE the "locations" table in
a security-findings doc; use scrub_source.py (same folder) to actually redact.

    python scan_secrets.py <root>
    python scan_secrets.py <root> --exclude data02 data03 archive

`<root>` defaults to the current directory. Project-agnostic: no paths are baked in.
"""
import argparse
import os
import re
import sys
from collections import Counter, defaultdict

# (label, pattern). Patterns capture the assignment shape, not the value.
RULES = [
    ("SMTP/API password", re.compile(r"\bc?password\s*=\s*[\"']", re.I)),
    ("SMTP/API username", re.compile(r"\bc?username\s*=\s*[\"']", re.I)),
    ("FTP password", re.compile(r"\bftp\w*pass\w*\s*=\s*[\"']", re.I)),
    ("FTP user", re.compile(r"\bftp\w*user\w*\s*=\s*[\"']", re.I)),
    ("FTP login line", re.compile(r"[\"']\s*user\s+\w+\s+\S+[\"']", re.I)),
    ("hardcoded host/IP", re.compile(r"[\"']\d{1,3}(\.\d{1,3}){3}[\"']")),
    ("connection string", re.compile(r"\b(pwd|passwd)\s*=", re.I)),
]

DEFAULT_EXTS = (".prg", ".sc2", ".vc2", ".fr2", ".mnx", ".bat", ".ini")


def main():
    ap = argparse.ArgumentParser(description="Locate (never print) hardcoded credentials in VFP source.")
    ap.add_argument("root", nargs="?", default=".", help="source folder to scan (default: .)")
    ap.add_argument("--ext", nargs="+", default=list(DEFAULT_EXTS), help="file extensions to scan")
    ap.add_argument("--exclude", nargs="*", default=[], help="directory names to skip")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    exts = tuple(e if e.startswith(".") else "." + e for e in (x.lower() for x in args.ext))
    exclude = {e.lower() for e in args.exclude}

    hits = defaultdict(list)          # label -> [(relpath, lineno)]
    files = set()

    for r, dirs, fs in os.walk(root):
        dirs[:] = [d for d in dirs if d.lower() not in exclude]
        for fn in fs:
            if not fn.lower().endswith(exts):
                continue
            p = os.path.join(r, fn)
            try:
                with open(p, encoding="latin-1") as fh:
                    for i, line in enumerate(fh, 1):
                        for label, rx in RULES:
                            if rx.search(line):
                                rel = os.path.relpath(p, root)
                                hits[label].append((rel, i))
                                files.add(rel)
            except OSError:
                continue

    total = sum(len(v) for v in hits.values())
    print(f"secret-shaped assignments: {total} across {len(files)} files")
    print("(values intentionally not shown)\n")
    for label in sorted(hits, key=lambda k: -len(hits[k])):
        locs = hits[label]
        byfile = Counter(f for f, _ in locs)
        print(f"{label:<22} {len(locs):>4} occurrence(s) in {len(byfile)} file(s)")
        for f, n in byfile.most_common(6):
            print(f"    {f}  x{n}")
    print()

    ext = Counter(os.path.splitext(f)[1].lower() for f in files)
    print("affected file types:", dict(ext))
    return 0


if __name__ == "__main__":
    sys.exit(main())
