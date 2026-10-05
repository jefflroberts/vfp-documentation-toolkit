@echo off
REM ===================================================================
REM  Pre-flight self-test for the portable converter. Run this FIRST.
REM
REM  Usage:
REM     self_test.bat                       (environment checks only)
REM     self_test.bat  "C:\path\to\vfp\data"   (also test reading real data)
REM ===================================================================
setlocal
set HERE=%~dp0

set PY=python
if exist "%HERE%python\python.exe" set PY="%HERE%python\python.exe"

if "%~1"=="" (
    %PY% "%HERE%self_test.py"
) else (
    %PY% "%HERE%self_test.py" --data "%~1"
)
echo.
pause
