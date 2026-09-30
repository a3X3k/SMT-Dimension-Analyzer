@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (set PY=py) else (set PY=python)
%PY% app.py
