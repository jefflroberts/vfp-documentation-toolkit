"""
Scrub credential VALUES out of VFP source before the first git commit.

SURGICAL by design: it only replaces the quoted value in a credential assignment
(or the login/password tokens of an FTP `user X Y` command string) with the literal
REDACTED. Variable names, structure, quotes and line count are preserved, so the code
still compiles and doc file:line references stay valid.

It deliberately does NOT touch bare English words, hostnames, or IP addresses -- only
values attached to a credential-shaped key. Idempotent: re-running finds nothing.

Reporting shows file:line, the credential KEY (variable name -- safe), and the value
LENGTH. It never prints the value.

    python scrub_source.py <root>            # dry run  (report only, no writes)
    python scrub_source.py <root> --apply    # rewrite the files in place
    python scrub_source.py <root> --ext .prg .sc2 .vc2 .fr2 --exclude data02 archive

`<root>` defaults to the current directory. This tool is project-agnostic: point it
at the folder holding the VFP source. Pair it with the pre-commit hook in this folder
so a fresh production copy can never be committed with live credentials.
"""
import argparse
import os
import sys

import re

PLACE = "REDACTED"

# (kind, regex, per-rule placeholder). Each regex has a named group 'v' = the secret
# value to blank, and (except ftp-login) a group 'k' = the key name (safe to print).
# The rules are intentionally generic VFP/credential shapes -- no project specifics.
RULES = [
    ("password",  re.compile(r"(?P<k>\b[A-Za-z_]*pass(?:word|wd)?)\s*=\s*(?P<q>[\"'])(?P<v>.*?)(?P=q)", re.I), PLACE),
    ("pwd=",      re.compile(r"(?P<k>\bpwd)\s*=\s*(?P<q>[\"'])(?P<v>.*?)(?P=q)", re.I), PLACE),
    ("username",  re.compile(r"(?P<k>\b[A-Za-z_]*username)\s*=\s*(?P<q>[\"'])(?P<v>.*?)(?P=q)", re.I), PLACE),
    ("ftpuser",   re.compile(r"(?P<k>\bftp[A-Za-z_]*user[A-Za-z_]*)\s*=\s*(?P<q>[\"'])(?P<v>.*?)(?P=q)", re.I), PLACE),
    ("login=",    re.compile(r"(?P<k>\blogin)\s*=\s*(?P<q>[\"'])(?P<v>.*?)(?P=q)", re.I), PLACE),
    # FTP command string: "user <login> <pass>"  ->  "user REDACTED REDACTED".
    # Case-SENSITIVE lowercase 'user' anchored to the quote, so it hits real FTP
    # commands ("user someuser somepass") but never captions ("User Not Found",
    # "Selected user ...").
    ("ftp-login", re.compile(r"(?P<q>[\"'])user\s+(?P<v>\S+\s+\S+?)\s*(?P=q)"), PLACE + " " + PLACE),
]

DEFAULT_EXTS = {".prg", ".sc2", ".vc2"}


# Skip only genuinely-empty inits and already-scrubbed values. A value that happens to
# be a weak word like "password" is still a real credential when attached to a cred key,
# so it must be scrubbed -- do NOT stoplist it.
def _skip(v):
    return (not v.strip()) or (set(v.split()) <= {PLACE})


def iter_src(root, exts, exclude):
    exclude = {e.lower() for e in exclude}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d.lower() not in exclude]
        for f in files:
            if os.path.splitext(f)[1].lower() in exts:
                yield os.path.join(base, f)


def scrub_text(text, path, records):
    def make(kind, place):
        def repl(m):
            val = m.group("v")
            if _skip(val):
                return m.group(0)
            lineno = text.count("\n", 0, m.start()) + 1
            key = (m.groupdict().get("k") or "user").strip()
            records.append((path, lineno, kind, key, len(val)))
            s, a, b = m.group(0), m.start("v") - m.start(0), m.end("v") - m.start(0)
            return s[:a] + place + s[b:]
        return repl
    for kind, rx, place in RULES:
        text = rx.sub(make(kind, place), text)
    return text


def main():
    ap = argparse.ArgumentParser(description="Scrub credential values out of VFP source.")
    ap.add_argument("root", nargs="?", default=".", help="source folder to scrub (default: .)")
    ap.add_argument("--apply", action="store_true", help="rewrite files in place (default: dry run)")
    ap.add_argument("--ext", nargs="+", default=sorted(DEFAULT_EXTS),
                    help="file extensions to scan (default: .prg .sc2 .vc2)")
    ap.add_argument("--exclude", nargs="*", default=[],
                    help="directory names to skip (e.g. archive company folders)")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    exts = {e if e.startswith(".") else "." + e for e in (x.lower() for x in args.ext)}

    records, changed = [], 0
    for path in iter_src(root, exts, args.exclude):
        with open(path, encoding="latin-1", newline="") as fh:
            orig = fh.read()
        new = scrub_text(orig, path, records)
        if new != orig:
            changed += 1
            if args.apply:
                with open(path, "w", encoding="latin-1", newline="") as fh:
                    fh.write(new)

    rel = lambda p: os.path.relpath(p, root)  # noqa: E731
    by_file = {}
    for p, ln, kind, key, n in records:
        by_file.setdefault(rel(p), []).append((ln, kind, key, n))
    for f in sorted(by_file):
        print(f"\n{f}")
        for ln, kind, key, n in sorted(by_file[f]):
            print(f"    line {ln:<5} {kind:<10} key={key:<20} value_len={n}")

    print(f"\n{'APPLIED' if args.apply else 'DRY RUN'}: {len(records)} value(s) "
          f"across {changed} file(s)"
          + ("" if args.apply else "  --  re-run with --apply to write"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
