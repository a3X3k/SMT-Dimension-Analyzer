@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo SMT Dimension Analyzer - Windows EXE Builder
echo ==============================================
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set PY=py
) else (
  set PY=python
)
%PY% -m pip install --upgrade pip
if errorlevel 1 goto :fail
%PY% -m pip install -r requirements-build.txt
if errorlevel 1 goto :fail
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
%PY% -m PyInstaller --clean --noconfirm SMT_Dimension_Analyzer.spec
if errorlevel 1 goto :fail
echo.
echo Build complete.
echo EXE: %CD%\dist\SMT_Dimension_Analyzer.exe
echo You can copy this EXE to another Windows PC.
pause
exit /b 0
:fail
echo.
echo BUILD FAILED. Review the error messages above.
pause
exit /b 1
