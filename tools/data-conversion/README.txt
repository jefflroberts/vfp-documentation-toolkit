===================================================================
 Portable VFP database (.dbc) -> SQLite converter
===================================================================

WHAT THIS IS
------------
It reads a Visual FoxPro database folder (a .dbc container + the .dbf/.fpt files)
and writes a single appdata.sqlite, recovering the FULL (long) field names
from the .dbc container so the parity queries run as written.

It is meant to run ON THE CLIENT'S OLD MACHINES (Windows XP / Windows 7)
during the early parity phase, and it produces appdata.sqlite directly there.

VERIFIED: produces output byte-identical (every table: schema + row counts +
content hashes) to the modern-Python version it was ported from.

WHICH .DBC: the converter finds the container itself. If the data folder
holds one .dbc it uses that; if it holds several it uses appdata.dbc, and
if none of them is appdata.dbc it stops and lists them so you can pick one
with --dbc (or build.bat's third argument). It prints the one it chose.


WHAT'S IN THIS FOLDER
---------------------
  build_appdata_sqlite_portable.py   the converter (Python 3.4-compatible)
  dbfread\                           bundled .dbf reader (no pip needed)
  build.bat                          double-click / command-line launcher
  self_test.py                       pre-flight check -- RUN THIS FIRST
  self_test.bat                      launcher for the pre-flight check
  python-3.4.4.msi                   the interpreter, committed (32-bit, last CPython for XP)
  README.txt                         this file

  NOT in the repo -- you stage these yourself before a visit (see STAGING):
  python\                            interpreter extracted from the MSI
  msvcr100.dll, msvcp100.dll         VC++ 2010 runtime, next to python.exe
  vcredist_2010sp1_x86.exe           on-site fallback installer

  They are .gitignored deliberately: python\ is ~59 MB / 3,400 files derivable
  from the committed MSI in one command, and the DLLs are redistributables.
  What the repo guarantees is that you can REBUILD the kit from a clean clone.

  CAVEAT: a clone gets you steps 1 and 4 of STAGING. The DLLs (step 2) are NOT
  obtainable from this repo and were not present on the dev machine either --
  source them before you travel.


REQUIREMENTS
------------
Just CPython. NOTHING needs to be pip-installed -- dbfread is bundled, and
sqlite3 ships inside Python itself.

  * Windows XP : Python 3.4.4  (this is the LAST CPython that runs on XP).
                 python-3.4.4.msi is committed in this folder -- no download.
  * Windows 7  : Python 3.4.4 also works; or anything up to Python 3.8
                 (3.9+ does NOT run on Windows 7).

The same 3.4.4 build covers BOTH XP and Win 7, so standardize on it.

You also need the VC++ 2010 runtime -- see STAGING. This is not optional and
it is the one thing that will silently sink a visit if you skip it.


STAGING (do this ONCE, on your dev machine, before going on-site)
-----------------------------------------------------------------
Produces a USB stick that needs nothing installed on the client machine.
Verified end-to-end 2026-08-13.

  1. Extract the interpreter from the committed MSI WITHOUT installing it.
     An administrative install just unpacks the payload:

         msiexec /a python-3.4.4.msi /qb TARGETDIR=%CD%\python

     You should end up with  .\python\python.exe  (build.bat and self_test.bat
     auto-prefer it over whatever is on PATH).

  2. Put the VC++ 2010 runtime DLLs NEXT TO python.exe:

         .\python\msvcr100.dll
         .\python\msvcp100.dll

     WHY THIS MATTERS: Python 3.4 links against the VC++ 2010 runtime. Without
     it python.exe dies instantly with exit code -1073741515 (0xC0000135,
     STATUS_DLL_NOT_FOUND) printing NOTHING on stdout or stderr -- it just
     returns. Easy to misread as "the script did nothing".

     Do not assume any machine has it. Reproduced 2026-08-13 on BOTH the Win 11
     laptop staged from and the Win 11 dev box: neither had msvcr100.dll
     anywhere on disk, and a freshly extracted 3.4.4 failed exactly this way.

     Copy them from a machine that has them (C:\Windows\SysWOW64) or extract
     them from vcredist. Verify with:  .\python\python.exe -c "import sqlite3"
     -- it must print nothing AND exit 0. Exit -1073741515 means missing DLLs.

  3. Drop vcredist_2010sp1_x86.exe at the kit root as an on-site fallback,
     in case you hit a machine where the local-DLL trick is blocked.

  4. Run the pre-flight check on your own machine first:

         self_test.bat

     It must print RESULT: PASS using the bundled interpreter.

  5. Copy the whole folder to the USB drive.

On each client machine:

  1. Plug in the USB drive. Run the pre-flight check FIRST, pointed at the
     machine's real VFP data folder:
         self_test.bat "C:\path\to\their\vfp\data"
     Make sure it prints  RESULT: PASS  before continuing.
  2. Run the conversion:
         build.bat "C:\path\to\their\vfp\data"
     appdata.sqlite is written next to build.bat (i.e. on the USB drive).
  3. Take the USB drive back; the appdata.sqlite is your legacy parity snapshot.

  WATCH THE DATA FOLDER: installs carry decoys. On both machines seen so far
  the live folder was plain "data\", while the reassuringly-named
  "data_Current\" and "data_new\" were years stale. Check the modified date on
  the busiest table (orders, say) in each candidate, or just copy the whole app
  folder and sort it out later with tools/dbfscan.py, which compares record
  counts and key ranges across copies of the data.


HOW TO RUN
----------
Pre-flight check (do this first on any new machine):

    self_test.bat "C:\path\to\vfp\data"      (or: self_test.bat with no args)

It verifies Python version/bitness, the bundled dbfread, sqlite3, and -- if
given a data folder -- that the .dbc and a real .dbf actually read. It must
print "RESULT: PASS" before you trust a conversion.

Option A -- with build.bat (easiest):

    build.bat "C:\path\to\vfp\data"

  where "...\data" is the folder that contains the .dbc and the .dbf files.
  Output appdata.sqlite is written next to build.bat.

  To choose the output location:
    build.bat "C:\path\to\vfp\data"  "D:\out\appdata.sqlite"

  To choose the container too (only needed when there are several):
    build.bat "C:\path\to\vfp\data"  "D:\out\appdata.sqlite"  "C:\path\to\vfp\data\shop.dbc"

  To use a "data" folder you've copied next to build.bat, just run:
    build.bat

Option B -- call Python directly:

    python build_appdata_sqlite_portable.py --data "C:\path\to\vfp\data"
    python build_appdata_sqlite_portable.py --data "...\data" --out "...\appdata.sqlite"
    python build_appdata_sqlite_portable.py --data "...\data" --dbc "...\shop.dbc"

  Defaults: --out  = appdata.sqlite next to the script
            --dbc  = the only .dbc in <data> (appdata.dbc if there are several)


NOTES
-----
* Re-runnable: it deletes and rebuilds the output .sqlite each run.
* If the .dbc can't be read, it falls back to the truncated physical field
  names and prints a WARNING (queries written against the long names won't
  run, so make sure the .dbc is in the data folder).
* A per-table report prints at the end (rows / cols / name source). "renamed"
  counts how many columns were restored to their long .dbc names.
* This file also runs unchanged on modern Python 3.x, so you can build the
  same .sqlite on your dev machine for spot-checks.
