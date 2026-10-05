# Credential scrubbing & secret scanning (stage 0 safety)

The one thing you must do **before the first `git commit`** of a legacy VFP app:
make sure its hard-coded credentials never enter git history. VFP apps routinely
embed SMTP/API keys, FTP/SFTP logins, and DB passwords as string literals in
`.prg`/`.sc2`/`.vc2` source. This folder is the reusable guard.

Built on a real VFP 6 job, where the source carried dozens of credential-shaped
assignments across many files. Paths are parameterized — nothing here is
project-specific.

| Tool | What it does |
|---|---|
| `scan_secrets.py` | **Locates** credential-shaped assignments and prints `file:line` + the *kind* only. Never prints a value. Use it to write the "locations" table in a security-findings doc. |
| `scrub_source.py` | **Redacts** the credential *value* in place (→ `REDACTED`), surgically: only the quoted value of a credential-shaped key (and FTP `user X Y` command strings). Preserves line count and quotes, so code still compiles and `file:line` doc references stay valid. Idempotent. Dry-run by default; `--apply` to write. |
| `pre-commit` | Git hook that runs `scrub_source.py` in dry-run and **blocks the commit** if any live credential remains. |

## Usage

```sh
# See where the secrets are (safe — prints locations, never values):
python tools/security/scan_secrets.py path/to/source

# Preview what would be redacted (dry run):
python tools/security/scrub_source.py path/to/source

# Actually redact, then commit:
python tools/security/scrub_source.py path/to/source --apply

# Narrow scope (skip archive company folders, add report dumps):
python tools/security/scrub_source.py path/to/source --exclude data02 data03 archive --ext .prg .sc2 .vc2 .fr2
```

Install the hook once per clone (git does not clone hooks):

```sh
cp tools/security/pre-commit .git/hooks/pre-commit    # + chmod +x on Unix
```

The hook auto-detects `scrub_source.py` and scans the repo root by default.
Override with env vars if your layout differs:

```sh
SCRUB_ROOT=AppSource SCRUB_ARGS="--exclude data02 data03" git commit -m "..."
```

## Important caveats

- **Scrubbing the working tree does not undo prior exposure.** If credentials
  were ever pushed, **rotate them** — a redacted repo only prevents *future*
  leaks.
- **`custom\` shadows and compiled copies.** A secret often exists in more than
  one place (a `custom\` override, a `.vcx` backup, a compiled `.exe`). Scrub the
  source, then hunt duplicates and delete stale binaries.
- Re-run `scrub_source.py --apply` on **every** fresh pull from production before
  committing. The pre-commit hook enforces this, but only if it's installed.
- These regexes catch the common VFP credential shapes; they are not a proof of
  absence. Skim `scan_secrets.py` output and add rules for any project-specific
  key names (e.g. a bespoke `sitepass`/`tppass`).
