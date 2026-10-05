@echo off
REM ===================================================================
REM  VFP database (.dbc)  ->  appdata.sqlite   (PORTABLE / on-site tool)
REM
REM  Usage:
REM     build.bat  "C:\path\to\vfp\data"  [output.sqlite]  [container.dbc]
REM
REM  - Arg 1 = the VFP data folder (the one containing the .dbc and the
REM            .dbf files). If omitted, defaults to a "data" folder next to
REM            this .bat.
REM  - Arg 2 = output sqlite path (optional; defaults to appdata.sqlite next
REM            to this .bat).
REM  - Arg 3 = the .dbc container (optional; defaults to the only .dbc in
REM            the data folder, or appdata.dbc if there are several).
REM
REM  Python lookup order:
REM     1. a bundled .\python\python.exe  (drop a Python 3.4 install here to
REM        make this folder 100%% self-contained -- see README.txt)
REM     2. "python" on the PATH
REM ===================================================================
setlocal
set HERE=%~dp0

set PY=python
if exist "%HERE%python\python.exe" set PY="%HERE%python\python.exe"

set SCRIPT=%HERE%build_appdata_sqlite_portable.py

if "%~1"=="" (
    %PY% "%SCRIPT%"
    goto done
)
if "%~2"=="" (
    %PY% "%SCRIPT%" --data "%~1"
    goto done
)
if "%~3"=="" (
    %PY% "%SCRIPT%" --data "%~1" --out "%~2"
    goto done
)
%PY% "%SCRIPT%" --data "%~1" --out "%~2" --dbc "%~3"

:done
echo.
pause
